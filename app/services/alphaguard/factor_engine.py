"""Deterministic, snapshot-only factor calculation and immutable persistence."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import FactorDefinition, FactorResult

from .factor_registry import DefinitionConflictError, builtin_factor_definitions
from .paper_storage import to_mongo_value
from .quant_audit_service import QuantAuditService
from .quant_config import sha256_value
from .snapshot_data_resolver import ResolvedSnapshotData


class FactorCalculationError(ValueError):
    pass


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _series(rows: list[dict[str, Any]], field: str) -> list[float] | None:
    values = [_number(row.get(field)) for row in rows]
    return None if any(value is None for value in values) else [float(value) for value in values]


def _tail(values: list[float] | None, count: int) -> list[float] | None:
    return values[-count:] if values is not None and len(values) >= count else None


def _ratio(current: float, base: float) -> float | None:
    return None if abs(base) < 1e-12 else current / base - 1.0


def _aligned_returns(
    stocks: list[dict[str, Any]], benchmark: list[dict[str, Any]], periods: int
) -> tuple[float, float] | None:
    stock_map = {
        str(row.get("trade_date") or row.get("date")): _number(row.get("close"))
        for row in stocks
    }
    benchmark_map = {
        str(row.get("trade_date") or row.get("date")): _number(row.get("close"))
        for row in benchmark
    }
    dates = sorted(
        date_key
        for date_key in set(stock_map) & set(benchmark_map)
        if stock_map[date_key] is not None and benchmark_map[date_key] is not None
    )
    if len(dates) < periods + 1:
        return None
    dates = dates[-(periods + 1) :]
    stock_return = _ratio(float(stock_map[dates[-1]]), float(stock_map[dates[0]]))
    benchmark_return = _ratio(
        float(benchmark_map[dates[-1]]), float(benchmark_map[dates[0]])
    )
    if stock_return is None or benchmark_return is None:
        return None
    return stock_return, benchmark_return


def _report_date(row: dict[str, Any]) -> str:
    return str(row.get("report_period") or row.get("end_date") or "")[:10]


def _financial_pair(
    rows: list[dict[str, Any]], aliases: tuple[str, ...]
) -> tuple[float, float] | None:
    usable = []
    for row in rows:
        value = next((_number(row.get(alias)) for alias in aliases if row.get(alias) is not None), None)
        period = _report_date(row)
        if value is not None and len(period) == 10:
            usable.append((period, value))
    if not usable:
        return None
    usable.sort()
    current_period, current = usable[-1]
    prior_period = f"{int(current_period[:4]) - 1}{current_period[4:]}"
    prior = next((value for period, value in usable if period == prior_period), None)
    return None if prior is None else (current, prior)


def _latest_financial(
    rows: list[dict[str, Any]], aliases: tuple[str, ...]
) -> float | None:
    for row in sorted(rows, key=_report_date, reverse=True):
        for alias in aliases:
            value = _number(row.get(alias))
            if value is not None:
                return value
    return None


def _percentile(values: list[float], current: float) -> float:
    return 100.0 * sum(value <= current for value in values) / len(values)


def _event_risk(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    scores = []
    critical = (
        "退市",
        "立案",
        "处罚",
        "违约",
        "停牌",
        "重大诉讼",
        "控制权变更",
        "delist",
        "default",
        "fraud",
    )
    elevated = ("减持", "质押", "亏损", "下修", "诉讼", "investigation", "loss")
    for row in rows:
        explicit = str(
            row.get("risk_level")
            or row.get("severity")
            or row.get("importance")
            or ""
        ).upper()
        if explicit in {"CRITICAL", "BLOCKING"}:
            scores.append(100.0)
            continue
        if explicit == "HIGH":
            scores.append(75.0)
            continue
        if explicit in {"MEDIUM", "IMPORTANT"}:
            scores.append(50.0)
            continue
        if explicit == "LOW":
            scores.append(20.0)
            continue
        text = " ".join(
            str(row.get(field) or "")
            for field in ("title", "summary", "content", "category")
        ).lower()
        if any(keyword.lower() in text for keyword in critical):
            scores.append(100.0)
        elif any(keyword.lower() in text for keyword in elevated):
            scores.append(60.0)
        else:
            scores.append(0.0)
    return max(scores)


def _calculate(factor_id: str, data: ResolvedSnapshotData, parameters: dict) -> float | None:
    prices = data.prices
    closes = _series(prices, "close")
    if factor_id == "close_vs_ma20_v1":
        values = _tail(closes, 20)
        return None if values is None else _ratio(values[-1], statistics.fmean(values))
    if factor_id == "close_vs_ma60_v1":
        values = _tail(closes, 60)
        return None if values is None else _ratio(values[-1], statistics.fmean(values))
    if factor_id == "ma20_vs_ma60_v1":
        values = _tail(closes, 60)
        return None if values is None else _ratio(statistics.fmean(values[-20:]), statistics.fmean(values))
    if factor_id == "ma20_slope_5d_v1":
        values = _tail(closes, 25)
        return None if values is None else _ratio(statistics.fmean(values[-20:]), statistics.fmean(values[:20]))
    if factor_id in {"momentum_20d_v1", "momentum_60d_v1"}:
        periods = 20 if "20d" in factor_id else 60
        values = _tail(closes, periods + 1)
        return None if values is None else _ratio(values[-1], values[0])
    if factor_id == "relative_strength_hs300_20d_v1":
        aligned = _aligned_returns(prices, data.benchmark_prices, 20)
        return None if aligned is None else aligned[0] - aligned[1]
    if factor_id == "volume_confirmation_20d_v1":
        volumes = _tail(_series(prices, "volume"), 21)
        return None if volumes is None or statistics.median(volumes[:-1]) <= 0 else volumes[-1] / statistics.median(volumes[:-1])
    if factor_id in {"revenue_yoy_v1", "adjusted_net_profit_yoy_v1"}:
        aliases = (
            ("revenue", "oper_rev")
            if factor_id == "revenue_yoy_v1"
            else ("adjusted_net_profit", "profit_dedt", "deducted_net_profit")
        )
        pair = _financial_pair(data.financials, aliases)
        return None if pair is None else _ratio(pair[0], pair[1])
    if factor_id == "roe_v1":
        value = _latest_financial(data.financials, ("roe", "roe_waa", "roe_dt"))
        return None if value is None else (value / 100.0 if abs(value) > 1.5 else value)
    if factor_id == "operating_cashflow_to_profit_v1":
        cash = _latest_financial(data.financials, ("n_cashflow_act", "operating_cashflow"))
        profit = _latest_financial(data.financials, ("net_income", "net_profit"))
        return None if cash is None or profit is None or abs(profit) < 1e-12 else cash / profit
    if factor_id in {"pe_ttm_percentile_3y_v1", "pb_percentile_3y_v1"}:
        aliases = ("pe_ttm", "pe") if factor_id.startswith("pe_") else ("pb",)
        history = []
        for row in prices[-756:]:
            value = next((_number(row.get(alias)) for alias in aliases if row.get(alias) is not None), None)
            if value is not None and value > 0:
                history.append(value)
        minimum = int(parameters.get("min_samples", 60))
        return None if len(history) < minimum else _percentile(history, history[-1])
    if factor_id == "dividend_yield_v1":
        value = next(
            (
                _number(prices[-1].get(alias))
                for alias in ("dv_ttm", "dv_ratio", "dividend_yield")
                if prices and prices[-1].get(alias) is not None
            ),
            None,
        )
        return None if value is None else (value / 100.0 if value > 1 else value)
    if factor_id == "atr14_pct_v1":
        rows = prices[-15:]
        if len(rows) < 15:
            return None
        true_ranges = []
        for index, row in enumerate(rows[1:], start=1):
            high, low, previous = (
                _number(row.get("high")),
                _number(row.get("low")),
                _number(rows[index - 1].get("close")),
            )
            if high is None or low is None or previous is None:
                return None
            true_ranges.append(max(high - low, abs(high - previous), abs(low - previous)))
        close = _number(rows[-1].get("close"))
        return None if close is None or close <= 0 else statistics.fmean(true_ranges) / close
    if factor_id == "volatility20_annualized_v1":
        values = _tail(closes, 21)
        if values is None or any(value <= 0 for value in values):
            return None
        returns = [values[index] / values[index - 1] - 1 for index in range(1, len(values))]
        return statistics.stdev(returns) * math.sqrt(250)
    if factor_id == "average_amount20_v1":
        values = _tail(_series(prices, "amount"), 20)
        return None if values is None else statistics.fmean(values)
    if factor_id == "turnover20_v1":
        values = _tail(_series(prices, "turnover_rate"), 20)
        return None if values is None else statistics.fmean(values)
    if factor_id == "short_term_excess_return5_v1":
        aligned = _aligned_returns(prices, data.benchmark_prices, 5)
        return None if aligned is None else aligned[0] - aligned[1]
    if factor_id == "event_risk_v1":
        return _event_risk(data.news + data.announcements)
    raise FactorCalculationError(f"unsupported factor: {factor_id}")


def _normalize(value: float, method: str, parameters: dict[str, Any]) -> float:
    lower = float(parameters["lower"])
    upper = float(parameters["upper"])
    if upper <= lower:
        raise FactorCalculationError("normalization upper bound must exceed lower bound")
    if method == "absolute_risk":
        value = abs(value)
        score = 100 * (value - lower) / (upper - lower)
    elif method == "log_linear":
        if value <= 0 or lower <= 0:
            score = 0.0
        else:
            score = 100 * (math.log(value) - math.log(lower)) / (
                math.log(upper) - math.log(lower)
            )
    elif method == "inverse_percentile":
        score = 100.0 - value
    else:
        score = 100 * (value - lower) / (upper - lower)
    return max(0.0, min(100.0, score))


def _direction(score: float, group: str) -> str:
    if group in {"VOLATILITY_RISK", "EVENT_RISK"}:
        return "NEGATIVE" if score >= 60 else ("POSITIVE" if score <= 40 else "NEUTRAL")
    return "POSITIVE" if score >= 60 else ("NEGATIVE" if score <= 40 else "NEUTRAL")


def _factor_input_refs(
    definition: FactorDefinition, data: ResolvedSnapshotData
) -> list[str]:
    documents = []
    if any(item.startswith("prices.") for item in definition.required_inputs):
        documents.extend(data.prices)
    if any(
        item.startswith("benchmark_prices.") for item in definition.required_inputs
    ):
        documents.extend(data.benchmark_prices)
    if any(item.startswith("financials.") for item in definition.required_inputs):
        documents.extend(data.financials)
    if "news" in definition.required_inputs:
        documents.extend(data.news)
    if "announcements" in definition.required_inputs:
        documents.extend(data.announcements)
    return sorted(
        {
            str(document["_reference"])
            for document in documents
            if document.get("_reference")
        }
    )


class FactorEngine:
    def __init__(self, db):
        self.db = db
        self.audit = QuantAuditService(db)

    async def calculate_all(
        self,
        data: ResolvedSnapshotData,
        *,
        trace_id: str | None = None,
        factor_ids: list[str] | None = None,
    ) -> list[FactorResult]:
        factor_set, definitions, _ = builtin_factor_definitions()
        if data.snapshot.factor_version_set != {
            definition.factor_id: definition.factor_version for definition in definitions
        }:
            raise FactorCalculationError(
                f"snapshot factor_version_set does not match {factor_set}"
            )
        selected = set(factor_ids or [item.factor_id for item in definitions])
        known = {item.factor_id for item in definitions}
        if not selected or not selected <= known:
            raise FactorCalculationError(
                "Champion FactorSet references unknown or empty factor ids"
            )
        results = []
        for definition in definitions:
            if definition.factor_id not in selected:
                continue
            results.append(await self.calculate(definition, data, trace_id=trace_id))
        return results

    async def calculate(
        self,
        definition: FactorDefinition,
        data: ResolvedSnapshotData,
        *,
        trace_id: str | None = None,
    ) -> FactorResult:
        identity = {
            "snapshot_id": data.snapshot.snapshot_id,
            "factor_id": definition.factor_id,
            "factor_version": definition.factor_version,
        }
        input_hash = sha256_value(
            {
                "snapshot_input_hash": data.input_hash,
                "factor_id": definition.factor_id,
                "factor_version": definition.factor_version,
                "code_hash": definition.code_hash,
                "parameter_hash": definition.parameter_hash,
            }
        )
        existing = await self.db["ag_factor_results"].find_one(identity)
        if existing:
            existing.pop("_id", None)
            stored = FactorResult.model_validate(existing)
            if (
                stored.input_hash != input_hash
                or stored.code_hash != definition.code_hash
                or stored.parameter_hash != definition.parameter_hash
            ):
                await self.audit.record(
                    "QUANT_INTEGRITY_CONFLICT",
                    snapshot_id=data.snapshot.snapshot_id,
                    entity_id=stored.result_id,
                    trace_id=trace_id,
                    details={"entity": "FactorResult", **identity},
                )
                raise DefinitionConflictError(
                    "immutable FactorResult identity conflicts with current inputs"
                )
            return stored
        try:
            raw = _calculate(definition.factor_id, data, definition.parameters)
            score = (
                None
                if raw is None
                else _normalize(raw, definition.normalization_method, definition.parameters)
            )
            relevant_refs = _factor_input_refs(definition, data)
            result = FactorResult(
                result_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:{data.snapshot.snapshot_id}:{definition.factor_id}:{definition.factor_version}:{input_hash}",
                    )
                ),
                **identity,
                group=definition.group,
                symbol=data.snapshot.symbol,
                market=data.snapshot.market,
                trade_date=data.snapshot.trade_date,
                raw_value=raw,
                normalized_score=score,
                direction="UNKNOWN" if score is None else _direction(score, definition.group),
                confidence=0.0 if score is None else 1.0,
                missing_reason=(
                    f"snapshot lacks required inputs: {', '.join(definition.required_inputs)}"
                    if score is None
                    else None
                ),
                input_refs=relevant_refs,
                input_hash=input_hash,
                code_hash=definition.code_hash,
                parameter_hash=definition.parameter_hash,
                calculated_at=datetime.utcnow(),
            )
        except Exception as exc:
            await self.audit.record(
                "FACTOR_CALCULATION_FAILED",
                snapshot_id=data.snapshot.snapshot_id,
                entity_id=definition.factor_id,
                trace_id=trace_id,
                details={"error_type": type(exc).__name__},
            )
            raise
        await self.db["ag_factor_results"].insert_one(
            to_mongo_value(result.model_dump(mode="python"))
        )
        await self.audit.record(
            "FACTOR_CALCULATED",
            snapshot_id=data.snapshot.snapshot_id,
            entity_id=result.result_id,
            trace_id=trace_id,
            details={"factor_id": definition.factor_id},
        )
        return result
