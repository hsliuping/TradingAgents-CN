"""
Post-analysis trade timing plan helpers.

The standard TradingAgents graph produces narrative decisions. This module
turns those decisions into a small, structured plan that the UI can display
and use to prefill simulated orders after user confirmation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional


TradePlan = Dict[str, Any]


class TradeTimingService:
    """Build and normalize swing-trading execution plans."""

    time_horizon = "5-20个交易日"

    def build_plan(
        self,
        *,
        request: Any,
        reports: Dict[str, Any],
        decision: Dict[str, Any],
        llm: Optional[Any] = None,
    ) -> TradePlan:
        context = self._build_context(request, reports, decision)
        if llm is not None:
            plan = self._build_llm_plan(context, llm)
            if plan:
                return self.normalize_plan(plan, request=request, reports=reports, decision=decision)
        return self._build_fallback_plan(context)

    def normalize_plan(
        self,
        raw_plan: Dict[str, Any],
        *,
        request: Any,
        reports: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> TradePlan:
        fallback = self._build_fallback_plan(self._build_context(request, reports, decision))
        if not isinstance(raw_plan, dict):
            return fallback

        action = self._normalize_action(raw_plan.get("action") or fallback["action"])
        entry_zone = self._normalize_entry_zone(raw_plan.get("entry_zone"), fallback["entry_zone"])
        stop_loss = self._normalize_price_block(raw_plan.get("stop_loss"), fallback["stop_loss"], "reason")
        take_profit = self._normalize_price_block(raw_plan.get("take_profit"), fallback["take_profit"], "strategy")
        invalidations = self._normalize_string_list(raw_plan.get("invalidations")) or fallback["invalidations"]

        return {
            "action": action,
            "entry_zone": entry_zone,
            "entry_trigger": self._string_or(raw_plan.get("entry_trigger"), fallback["entry_trigger"]),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "invalidations": invalidations,
            "time_horizon": self._string_or(raw_plan.get("time_horizon"), self.time_horizon),
            "position_hint": self._string_or(raw_plan.get("position_hint"), fallback["position_hint"]),
            "confidence": self._clamp(raw_plan.get("confidence"), fallback["confidence"]),
            "risk_level": self._normalize_risk_level(raw_plan.get("risk_level") or fallback["risk_level"]),
            "evidence_grade": self._normalize_evidence_grade(raw_plan.get("evidence_grade") or fallback["evidence_grade"]),
            "source": self._string_or(raw_plan.get("source"), "trade_timing_agent"),
        }

    def render_report(self, plan: TradePlan) -> str:
        action_label = {
            "buy": "买入",
            "sell": "卖出",
            "hold": "持有",
            "watch": "观望",
        }.get(plan.get("action"), "观望")
        entry = plan.get("entry_zone") or {}
        stop = plan.get("stop_loss") or {}
        target = plan.get("take_profit") or {}
        invalidations = plan.get("invalidations") or []

        lines = [
            "## 交易执行计划",
            "",
            f"- 动作参考：{action_label}",
            f"- 周期：{plan.get('time_horizon', self.time_horizon)}",
            f"- 入场观察区：{entry.get('text') or '暂无明确区间'}",
            f"- 入场触发：{plan.get('entry_trigger') or '等待更明确的价格信号'}",
            f"- 止损：{self._format_price(stop.get('price'))}（{stop.get('reason') or '暂无'}）",
            f"- 止盈：{target.get('zone') or self._format_price(target.get('price'))}（{target.get('strategy') or '分批止盈'}）",
            f"- 仓位提示：{plan.get('position_hint') or '不读取账户资金，仅提供通用比例参考'}",
            f"- 置信度：{self._clamp(plan.get('confidence'), 0.5):.0%}",
            f"- 风险等级：{plan.get('risk_level') or '中等'}",
            f"- 证据等级：{plan.get('evidence_grade') or 'C'}",
            "",
            "### 策略失效条件",
        ]
        lines.extend(f"- {item}" for item in invalidations)
        lines.append("")
        lines.append("说明：该计划只用于模拟交易预填和风险纪律参考，不读取账户持仓，不构成实盘投资建议。")
        return "\n".join(lines)

    def _build_context(self, request: Any, reports: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
        params = getattr(request, "parameters", None)
        symbol = request.get_symbol() if hasattr(request, "get_symbol") else getattr(request, "symbol", "")
        text = self._collect_text(reports, decision)
        levels = self._extract_price_levels(text, decision)
        return {
            "stock_code": symbol,
            "market_type": getattr(params, "market_type", "A股") if params else "A股",
            "decision": decision if isinstance(decision, dict) else {},
            "reports": reports if isinstance(reports, dict) else {},
            "text": text,
            "levels": levels,
        }

    def _build_llm_plan(self, context: Dict[str, Any], llm: Any) -> Optional[TradePlan]:
        prompt = (
            "你是 TradingAgents-CN 的 Trade Timing Agent。请把已有股票分析转换为波段交易执行计划。\n"
            "只返回 JSON，不要 Markdown。字段必须包含 action, entry_zone, entry_trigger, stop_loss, "
            "take_profit, invalidations, time_horizon, position_hint, confidence, risk_level, evidence_grade。\n"
            "action 只能是 buy/sell/hold/watch。周期默认 5-20个交易日。不要读取或假设账户持仓。\n"
            f"股票代码：{context['stock_code']}\n"
            f"市场类型：{context['market_type']}\n"
            f"结构化决策：{context['decision']}\n"
            f"可用价格位：{context['levels']}\n"
            f"报告摘要：{context['text'][:3000]}"
        )
        try:
            response = llm.invoke(prompt)
            content = getattr(response, "content", response)
            if not isinstance(content, str):
                return None
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return None
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _build_fallback_plan(self, context: Dict[str, Any]) -> TradePlan:
        decision = context.get("decision") if isinstance(context.get("decision"), dict) else {}
        levels = context.get("levels") if isinstance(context.get("levels"), dict) else {}
        action = self._normalize_action(decision.get("action") or self._infer_action(context.get("text", "")))
        confidence = self._clamp(decision.get("confidence"), 0.5)
        risk_score = self._clamp(decision.get("risk_score"), 0.5)
        risk_level = self._risk_level_from_score(risk_score)
        evidence_grade = self._evidence_grade(context.get("reports", {}), levels)

        current = levels.get("current_price")
        target = self._to_float(decision.get("target_price")) or levels.get("target_price") or levels.get("resistance")
        support = levels.get("support")
        resistance = levels.get("resistance")
        breakout = levels.get("breakout_buy")
        breakdown = levels.get("breakdown_sell")
        stop = levels.get("stop_loss")

        if stop is None and support is not None:
            stop = round(support * 0.97, 2)
        if target is None and current is not None:
            target = round(current * (1.12 if action == "buy" else 0.95), 2)

        entry_zone = self._entry_zone(action, current, support, breakout, breakdown)
        entry_trigger = self._entry_trigger(action, current, support, breakout, breakdown)
        stop_loss = {
            "price": stop,
            "reason": "跌破关键支撑或止损位，波段交易假设失效。" if stop is not None else "缺少可验证止损价，需等待更完整价格位。",
        }
        take_profit = {
            "price": target,
            "zone": self._zone_text(target, resistance) if target is not None or resistance is not None else "暂无明确止盈区",
            "strategy": "接近目标价或压力位时分批止盈，保留部分仓位观察趋势延续。",
        }
        invalidations = self._invalidations(evidence_grade, stop, support, breakout, breakdown, action)

        return {
            "action": action,
            "entry_zone": entry_zone,
            "entry_trigger": entry_trigger,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "invalidations": invalidations,
            "time_horizon": self.time_horizon,
            "position_hint": self._position_hint(action, evidence_grade),
            "confidence": confidence,
            "risk_level": risk_level,
            "evidence_grade": evidence_grade,
            "source": "trade_timing_agent",
        }

    def _collect_text(self, reports: Dict[str, Any], decision: Dict[str, Any]) -> str:
        pieces: List[str] = []
        if isinstance(decision, dict):
            pieces.append(json.dumps(decision, ensure_ascii=False))
        for key in (
            "market_report",
            "trader_investment_plan",
            "risk_management_decision",
            "final_trade_decision",
            "committee_scorecard",
            "committee_reconciliation",
            "codex_agent_report",
        ):
            value = reports.get(key) if isinstance(reports, dict) else None
            if isinstance(value, str) and value.strip():
                pieces.append(value.strip())
        return "\n".join(pieces)

    def _extract_price_levels(self, text: str, decision: Dict[str, Any]) -> Dict[str, Optional[float]]:
        return {
            "current_price": self._extract_first(text, [r"(?:当前价格|当前价|现价|股价)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "support": self._extract_first(text, [r"(?:支撑位|支撑价|关键支撑)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "resistance": self._extract_first(text, [r"(?:压力位|阻力位|关键压力|关键阻力)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "breakout_buy": self._extract_first(text, [r"(?:突破买入价|突破价|买入触发价)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "breakdown_sell": self._extract_first(text, [r"(?:跌破卖出价|卖出触发价|破位价)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "stop_loss": self._extract_first(text, [r"(?:止损位|止损价|止损)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
            "target_price": self._to_float(decision.get("target_price") if isinstance(decision, dict) else None)
            or self._extract_first(text, [r"(?:目标价格|目标价位|目标价|止盈价)[：:]?\s*[¥￥$]?(\d+(?:\.\d+)?)"]),
        }

    def _extract_first(self, text: str, patterns: Iterable[str]) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = self._to_float(match.group(1))
                if value is not None:
                    return value
        return None

    def _normalize_action(self, action: Any) -> str:
        text = str(action or "").strip().lower()
        if text in {"buy", "买入", "增持", "购买"}:
            return "buy"
        if text in {"sell", "卖出", "减持", "出售"}:
            return "sell"
        if text in {"watch", "观望", "等待"}:
            return "watch"
        if "买" in text or "buy" in text:
            return "buy"
        if "卖" in text or "sell" in text:
            return "sell"
        if "观望" in text or "wait" in text:
            return "watch"
        return "hold"

    def _infer_action(self, text: str) -> str:
        if "卖出" in text or "减持" in text or re.search(r"\bsell\b", text, re.IGNORECASE):
            return "sell"
        if "买入" in text or "增持" in text or re.search(r"\bbuy\b", text, re.IGNORECASE):
            return "buy"
        if "观望" in text:
            return "watch"
        return "hold"

    def _entry_zone(
        self,
        action: str,
        current: Optional[float],
        support: Optional[float],
        breakout: Optional[float],
        breakdown: Optional[float],
    ) -> Dict[str, Any]:
        if action == "buy":
            low = current or support
            high = breakout or current or support
        elif action == "sell":
            low = breakdown or support
            high = current or breakdown or support
        else:
            low = support
            high = breakout or current
        return {"low": low, "high": high, "text": self._range_text(low, high)}

    def _entry_trigger(
        self,
        action: str,
        current: Optional[float],
        support: Optional[float],
        breakout: Optional[float],
        breakdown: Optional[float],
    ) -> str:
        if action == "buy":
            if breakout is not None:
                return f"放量突破并站稳{breakout:.2f}，且未快速跌回突破位下方。"
            if support is not None:
                return f"回踩{support:.2f}附近企稳，成交量未明显萎缩。"
            return "等待放量突破或回踩企稳信号，不追高。"
        if action == "sell":
            if breakdown is not None:
                return f"跌破{breakdown:.2f}或反抽无法收复时考虑卖出。"
            if support is not None:
                return f"跌破{support:.2f}关键支撑时考虑卖出。"
            return "等待明确破位或风险事件触发后再执行卖出。"
        if current is not None:
            return f"当前以观察为主，只有重新站稳关键均线或突破{current:.2f}上方压力后再评估。"
        return "等待更明确的价格、成交量和风险信号。"

    def _invalidations(
        self,
        evidence_grade: str,
        stop: Optional[float],
        support: Optional[float],
        breakout: Optional[float],
        breakdown: Optional[float],
        action: str,
    ) -> List[str]:
        items: List[str] = []
        if evidence_grade == "D":
            items.append("缺少关键价格位或核心报告，交易计划仅可作为观察清单。")
        if stop is not None:
            items.append(f"收盘价跌破止损位{stop:.2f}。")
        elif support is not None:
            items.append(f"有效跌破支撑位{support:.2f}。")
        if action == "buy" and breakout is not None:
            items.append(f"突破{breakout:.2f}后快速回落且成交量放大。")
        if action == "sell" and breakdown is not None:
            items.append(f"跌破{breakdown:.2f}后快速收复，卖出信号失效。")
        items.append("公司基本面、重大新闻或市场系统性风险与原分析方向明显冲突。")
        return items

    def _position_hint(self, action: str, evidence_grade: str) -> str:
        if action not in {"buy", "sell"}:
            return "不读取账户资金；当前不建议新增模拟订单，可保留观察清单。"
        if evidence_grade in {"A", "B"}:
            return "不读取账户资金；单笔模拟交易参考计划资金的10%-20%，分批执行。"
        return "不读取账户资金；证据等级偏低，模拟交易参考计划资金的5%-10%或仅观察。"

    def _evidence_grade(self, reports: Dict[str, Any], levels: Dict[str, Optional[float]]) -> str:
        report_count = sum(1 for value in reports.values() if isinstance(value, str) and len(value.strip()) >= 20)
        price_count = sum(1 for value in levels.values() if value is not None)
        if price_count >= 5 and report_count >= 4:
            return "A"
        if price_count >= 3 and report_count >= 2:
            return "B"
        if price_count >= 1:
            return "C"
        return "D"

    def _risk_level_from_score(self, risk_score: float) -> str:
        if risk_score >= 0.7:
            return "高"
        if risk_score <= 0.35:
            return "低"
        return "中等"

    def _normalize_entry_zone(self, raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(raw, dict):
            low = self._to_float(raw.get("low"))
            high = self._to_float(raw.get("high"))
            text = self._string_or(raw.get("text"), self._range_text(low, high))
            return {"low": low, "high": high, "text": text}
        if isinstance(raw, str) and raw.strip():
            return {"low": fallback.get("low"), "high": fallback.get("high"), "text": raw.strip()}
        return fallback

    def _normalize_price_block(self, raw: Any, fallback: Dict[str, Any], extra_key: str) -> Dict[str, Any]:
        if isinstance(raw, dict):
            result = dict(fallback)
            result["price"] = self._to_float(raw.get("price")) if raw.get("price") is not None else fallback.get("price")
            for key in ("reason", "zone", "strategy"):
                if key in raw:
                    result[key] = self._string_or(raw.get(key), result.get(key, ""))
            if extra_key not in result:
                result[extra_key] = fallback.get(extra_key, "")
            return result
        if isinstance(raw, (int, float, str)):
            price = self._to_float(raw)
            if price is not None:
                result = dict(fallback)
                result["price"] = price
                return result
        return fallback

    def _normalize_string_list(self, raw: Any) -> List[str]:
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if isinstance(raw, str) and raw.strip():
            return [line.strip("- ").strip() for line in raw.splitlines() if line.strip("- ").strip()]
        return []

    def _normalize_risk_level(self, raw: Any) -> str:
        text = str(raw or "").strip()
        if text in {"低", "低风险"}:
            return "低"
        if text in {"高", "高风险"}:
            return "高"
        return "中等"

    def _normalize_evidence_grade(self, raw: Any) -> str:
        text = str(raw or "").strip().upper()
        return text if text in {"A", "B", "C", "D"} else "C"

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            if isinstance(value, str):
                value = (
                    value.replace("¥", "")
                    .replace("￥", "")
                    .replace("$", "")
                    .replace("元", "")
                    .replace("美元", "")
                    .strip()
                )
            number = float(value)
            return round(number, 2)
        except (TypeError, ValueError):
            return None

    def _clamp(self, value: Any, fallback: float) -> float:
        number = self._to_float(value)
        if number is None:
            return fallback
        return max(0.0, min(1.0, number))

    def _string_or(self, value: Any, fallback: str) -> str:
        text = str(value).strip() if value is not None else ""
        return text or fallback

    def _range_text(self, low: Optional[float], high: Optional[float]) -> str:
        if low is not None and high is not None:
            if low == high:
                return f"{low:.2f}附近"
            return f"{min(low, high):.2f}-{max(low, high):.2f}"
        if low is not None:
            return f"{low:.2f}附近"
        if high is not None:
            return f"{high:.2f}附近"
        return "暂无明确区间"

    def _zone_text(self, target: Optional[float], resistance: Optional[float]) -> str:
        if target is not None and resistance is not None:
            return self._range_text(min(target, resistance), max(target, resistance))
        if target is not None:
            return f"{target:.2f}附近"
        if resistance is not None:
            return f"{resistance:.2f}附近"
        return "暂无明确止盈区"

    def _format_price(self, price: Any) -> str:
        number = self._to_float(price)
        return f"{number:.2f}" if number is not None else "暂无"


trade_timing_service = TradeTimingService()
