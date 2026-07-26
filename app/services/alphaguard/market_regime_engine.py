"""Five-state, deterministic market regime calculation."""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import MarketRegimeResult

from .factor_registry import DefinitionConflictError
from .quant_audit_service import QuantAuditService
from .quant_config import regime_config, sha256_value
from .snapshot_data_resolver import ResolvedSnapshotData


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _market_metrics(
    data: ResolvedSnapshotData,
) -> tuple[dict[str, float | None], list[str], list[str]]:
    config = regime_config()
    closes = [_num(row.get("close")) for row in data.benchmark_prices]
    missing = []
    invalid = []
    metrics: dict[str, float | None] = {
        "benchmark_close_vs_ma20": None,
        "benchmark_close_vs_ma60": None,
        "benchmark_ma20_slope_5d": None,
        "benchmark_volatility20": None,
        "market_breadth": None,
        "amount_ratio20": None,
        "new_high_low_ratio": None,
        "industry_diffusion": None,
        "extreme_risk_flag": None,
    }
    required = int(config["required_benchmark_sessions"])
    if len(closes) < required or any(value is None or value <= 0 for value in closes[-required:]):
        missing.append("benchmark_prices.close[61]")
    else:
        values = [float(value) for value in closes]
        ma20 = statistics.fmean(values[-20:])
        ma60 = statistics.fmean(values[-60:])
        prior_ma20 = statistics.fmean(values[-25:-5])
        returns = [values[index] / values[index - 1] - 1 for index in range(len(values) - 20, len(values))]
        metrics.update(
            benchmark_close_vs_ma20=values[-1] / ma20 - 1,
            benchmark_close_vs_ma60=values[-1] / ma60 - 1,
            benchmark_ma20_slope_5d=ma20 / prior_ma20 - 1,
            benchmark_volatility20=statistics.stdev(returns) * math.sqrt(250),
        )

    if not data.market_context:
        missing.append("market_context")
    else:
        latest = data.market_context[-1]
        advances = _num(latest.get("advance_count"))
        declines = _num(latest.get("decline_count"))
        if (advances is not None and advances < 0) or (
            declines is not None and declines < 0
        ):
            invalid.append("market_context negative breadth counts")
            advances = declines = None
        if advances is not None and declines is not None and advances + declines > 0:
            metrics["market_breadth"] = (advances - declines) / (advances + declines)
        else:
            missing.append("market_context.advance_count/decline_count")
        diffusion_value = latest.get("industry_up_ratio")
        if diffusion_value is None:
            diffusion_value = latest.get("industry_diffusion")
        metrics["industry_diffusion"] = _num(diffusion_value)
        if metrics["industry_diffusion"] is None:
            missing.append("market_context.industry_diffusion")
        metrics["amount_ratio20"] = _num(latest.get("amount_ratio20"))
        highs, lows = _num(latest.get("new_high_count")), _num(latest.get("new_low_count"))
        if highs is not None and lows is not None and highs + lows > 0:
            metrics["new_high_low_ratio"] = (highs - lows) / (highs + lows)
        metrics["extreme_risk_flag"] = 1.0 if latest.get("extreme_risk_flag") is True else 0.0
        diffusion = metrics["industry_diffusion"]
        if diffusion is not None and not 0 <= diffusion <= 1:
            invalid.append("market_context industry_diffusion outside 0..1")
            metrics["industry_diffusion"] = None
    return metrics, missing, invalid


class MarketRegimeEngine:
    def __init__(self, db):
        self.db = db
        self.audit = QuantAuditService(db)

    async def calculate(
        self, data: ResolvedSnapshotData, *, trace_id: str | None = None
    ) -> MarketRegimeResult:
        config = regime_config()
        metrics, missing, invalid = _market_metrics(data)
        input_hash = sha256_value(
            {
                "snapshot_input_hash": data.input_hash,
                "regime_version": config["regime_version"],
                "metrics": metrics,
                "missing": missing,
                "invalid": invalid,
            }
        )
        existing = await self.db["ag_regime_results"].find_one(
            {
                "snapshot_id": data.snapshot.snapshot_id,
                "regime_version": config["regime_version"],
            }
        )
        if existing:
            existing.pop("_id", None)
            stored = MarketRegimeResult.model_validate(existing)
            if stored.input_hash != input_hash:
                await self.audit.record(
                    "QUANT_INTEGRITY_CONFLICT",
                    snapshot_id=data.snapshot.snapshot_id,
                    entity_id=stored.regime_result_id,
                    trace_id=trace_id,
                    details={"entity": "MarketRegimeResult"},
                )
                raise DefinitionConflictError("immutable MarketRegimeResult conflict")
            return stored

        status = "CALCULATED"
        regime = None
        evidence = []
        allow_new = False
        allowed = ["POSITION_EXIT_V1"]
        exposure = None
        confidence = 0.0
        thresholds = config["thresholds"]
        required_metrics = (
            "benchmark_close_vs_ma20",
            "benchmark_close_vs_ma60",
            "benchmark_ma20_slope_5d",
            "benchmark_volatility20",
            "market_breadth",
            "industry_diffusion",
        )
        if invalid:
            status = "INVALID_INPUT"
            evidence = [f"invalid:{item}" for item in sorted(set(invalid))]
        elif missing or any(metrics[key] is None for key in required_metrics):
            status = "INSUFFICIENT_DATA"
            evidence = [f"missing:{item}" for item in sorted(set(missing))]
        else:
            close20 = float(metrics["benchmark_close_vs_ma20"])
            close60 = float(metrics["benchmark_close_vs_ma60"])
            slope = float(metrics["benchmark_ma20_slope_5d"])
            volatility = float(metrics["benchmark_volatility20"])
            breadth = float(metrics["market_breadth"])
            diffusion = float(metrics["industry_diffusion"])
            extreme = bool(metrics["extreme_risk_flag"]) or (
                volatility >= thresholds["extreme_volatility"]
                and breadth <= thresholds["breadth_collapse"]
            )
            if extreme:
                regime = "EXTREME_RISK"
            elif (
                close20 > 0
                and close60 > 0
                and slope > 0
                and breadth >= thresholds["trend_breadth"]
                and diffusion >= thresholds["strong_diffusion"]
            ):
                regime = "TREND_UP"
            elif close60 < 0 and slope < 0 and breadth <= thresholds["weak_breadth"]:
                regime = "TREND_DOWN"
            elif close60 >= 0 and breadth >= 0:
                regime = "RANGE_STRONG"
            else:
                regime = "RANGE_WEAK"
            allowed = list(config["allowed_strategies"][regime])
            allow_new = regime in {"TREND_UP", "RANGE_STRONG"}
            exposure = float(config["exposure"][regime])
            confidence = 1.0
            evidence = [
                f"benchmark_close_vs_ma20={close20:.6f}",
                f"benchmark_close_vs_ma60={close60:.6f}",
                f"benchmark_ma20_slope_5d={slope:.6f}",
                f"benchmark_volatility20={volatility:.6f}",
                f"market_breadth={breadth:.6f}",
                f"industry_diffusion={diffusion:.6f}",
            ]

        result = MarketRegimeResult(
            regime_result_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:regime:{data.snapshot.snapshot_id}:{config['regime_version']}:{input_hash}",
                )
            ),
            snapshot_id=data.snapshot.snapshot_id,
            trade_date=data.snapshot.trade_date,
            calculation_status=status,
            regime=regime,
            confidence=confidence,
            evidence=evidence,
            metrics=metrics,
            allowed_strategy_ids=allowed,
            allow_new_positions=allow_new,
            max_total_exposure_pct=exposure,
            regime_version=config["regime_version"],
            input_hash=input_hash,
            calculated_at=datetime.utcnow(),
        )
        await self.db["ag_regime_results"].insert_one(result.model_dump(mode="python"))
        await self.audit.record(
            (
                "REGIME_CALCULATED"
                if status == "CALCULATED"
                else "REGIME_CALCULATION_FAILED"
            ),
            snapshot_id=data.snapshot.snapshot_id,
            entity_id=result.regime_result_id,
            trace_id=trace_id,
            details={"status": status, "regime": regime},
        )
        return result
