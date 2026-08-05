"""Low-cost, model-free candidate recommendation and review governance."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as datetime_time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from pymongo import InsertOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    mongo_date,
)
from tradingagents.alphaguard.candidate_schemas import CandidateSource, CandidateStatus
from tradingagents.alphaguard.recommendation_schemas import (
    CandidateEligibilityResult,
    CandidateRecommendation,
    CandidateRecommendationEvaluation,
    CandidateRecommendationPolicy,
    CandidateRecommendationReviewEvent,
    CandidateRecommendationRun,
    CandidateRecommendationScoreResult,
    CandidateUniverseManifest,
    RECOMMENDATION_ELIGIBILITY_SCHEMA_VERSION,
    RecommendationFactorEvidence,
    recommendation_hash,
)

from .candidate_recommendation_policy import CandidateRecommendationPolicyRegistry
from .recommendation_data_service import (
    RecommendationDataService,
    recommendation_data_contract,
)


_Q = Decimal("0.01")
_TERMINAL_ORDER_STATUSES = {
    "FILLED",
    "CANCELLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
}
_SOURCE_PRIORITY = {"tushare": 1, "akshare": 2, "baostock": 3}
_STATUS_BY_ACTION = {
    "ACCEPTED": "ACCEPTED",
    "REJECTED": "REJECTED",
    "IGNORED": "IGNORED",
    "SUPERSEDED": "SUPERSEDED",
    "EXPIRED": "EXPIRED",
}
_CANDIDATE_INPUT_CONTRACT_VERSION = "candidate-input-v3"
_FILTER_PRIORITY = (
    "DELISTED",
    "DELISTING_PERIOD",
    "ST_NOT_ALLOWED",
    "LISTING_DATE_MISSING",
    "LISTING_HISTORY_INSUFFICIENT",
    "TRADE_DATE_QUOTE_MISSING",
    "TRADING_STATUS_NOT_READY",
    "SUSPENDED",
    "DATA_QUALITY_FAILED",
    "DATA_QUALITY_NOT_AVAILABLE",
    "PRICE_HISTORY_INSUFFICIENT",
    "PRICE_DATA_ANOMALY",
    "LOW_LIQUIDITY",
    "LONG_NO_TRADE",
    "ALREADY_IN_CANDIDATE_POOL",
    "POSITION_REQUIRES_MONITORING",
    "UNFINISHED_ORDER",
    "ACTIVE_TRADE_PLAN",
    "PENDING_EVALUATION",
)


class RecommendationIntegrityConflict(RuntimeError):
    pass


class RecommendationReviewConflict(RuntimeError):
    pass


class CandidatePoolLimitReached(RuntimeError):
    pass


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    try:
        result = Decimal(str(value))
    except Exception:
        return default
    return result if result.is_finite() else default


def _money(value: Decimal) -> Decimal:
    return value.quantize(_Q, rounding=ROUND_HALF_UP)


def _stable_id(namespace: str, identity: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"alphaguard:{namespace}:{identity}"))


def _security_type(row: dict[str, Any]) -> str | None:
    labels = " ".join(
        str(row.get(key) or "")
        for key in ("security_type", "category", "sec", "type", "asset_type")
    ).lower()
    if "etf" in labels or "exchange_traded_fund" in labels:
        return "EXCHANGE_TRADED_FUND"
    if any(token in labels for token in ("stock_cn", "equity", "股票", "a_share")):
        return "A_SHARE"
    if str(row.get("source") or "").lower() == "baostock" and str(
        row.get("market") or ""
    ).upper() == "CN":
        return "A_SHARE"
    return None


def _quote_mode(row: dict[str, Any]) -> str:
    return str(
        row.get("price_adjustment_mode") or row.get("adjustment_mode") or ""
    ).upper()


def _quote_date(row: dict[str, Any]) -> date | None:
    return _as_date(row.get("trade_date") or row.get("date") or row.get("business_date"))


def _quote_ref(row: dict[str, Any]) -> str:
    return str(
        row.get("data_ref")
        or (f"stock_daily_quotes:{row['ref_id']}" if row.get("ref_id") else "")
        or row.get("source_record_id")
        or ""
    )


class CandidateRecommendationService:
    """One governed boundary for scans, reviews, and candidate acceptance."""

    def __init__(self, db):
        self.db = db
        self.policy_registry = CandidateRecommendationPolicyRegistry(db)

    async def resolve_latest_trade_date(self) -> date:
        quote_dates = {
            item
            for row in await self.db["market_quotes"].find({}).to_list(length=None)
            if (item := _quote_date(row)) is not None
        }
        if not quote_dates:
            raise LookupError("PERSISTED_FULL_MARKET_QUOTES_MISSING")
        calendar_rows = await self.db["trading_calendar"].find({}).to_list(length=None)
        open_dates = {
            item
            for row in calendar_rows
            if str(row.get("market") or "CN").upper() == "CN"
            and row.get("is_open") is True
            and (item := _as_date(
                row.get("trade_date") or row.get("session_date") or row.get("date")
            ))
            is not None
        }
        available = quote_dates & open_dates
        if not available:
            raise LookupError("PERSISTED_TRADING_CALENDAR_GATE_FAILED")
        return max(available)

    async def _load_universe_rows(self) -> list[dict[str, Any]]:
        rows = [
            clean_document(row)
            for row in await self.db["stock_basic_info"].find({}).to_list(length=None)
        ]
        selected: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = str(row.get("code") or row.get("symbol") or "").strip()
            security_type = _security_type(row)
            if len(symbol) != 6 or not symbol.isdigit() or security_type is None:
                continue
            row["_recommendation_security_type"] = security_type
            rank = (
                0 if row.get("security_master_content_hash") else 1,
                _SOURCE_PRIORITY.get(str(row.get("source") or "").lower(), 99),
                str(row.get("source") or ""),
            )
            current = selected.get(symbol)
            current_rank = current.get("_recommendation_rank") if current else None
            if current is None or rank < current_rank:
                row["_recommendation_rank"] = rank
                selected[symbol] = row
        return [selected[symbol] for symbol in sorted(selected)]

    async def build_universe_manifest(
        self,
        *,
        universe_date: date,
        policy: CandidateRecommendationPolicy,
        now: datetime,
        execute: bool = True,
    ) -> CandidateUniverseManifest:
        rows = await self._load_universe_rows()
        records = []
        for row in rows:
            symbol = str(row.get("code") or row.get("symbol"))
            listing_date = _as_date(
                row.get("list_date") or row.get("listing_date")
            )
            if listing_date is not None and listing_date > universe_date:
                continue
            source = str(row.get("source") or "unknown")
            source_ref = str(
                row.get("security_master_source_ref")
                or f"stock_basic_info:{symbol}:{source}"
            )
            content = {
                "symbol": symbol,
                "name": str(row.get("name") or symbol),
                "security_type": row["_recommendation_security_type"],
                "listing_date": listing_date.isoformat() if listing_date else "",
                "listing_status": str(
                    row.get("listing_status") or row.get("status") or ""
                ),
                "source": source,
                "source_ref": source_ref,
                "source_content_hash": str(
                    row.get("security_master_content_hash") or ""
                ),
            }
            records.append((symbol, row["_recommendation_security_type"], source_ref, recommendation_hash(content)))
        source_hash = recommendation_hash({"records": records})
        universe_version = f"{policy.universe_policy_version}:{universe_date.isoformat()}:{source_hash[:16]}"
        identity = f"CN:{universe_date.isoformat()}:{universe_version}"
        payload = {
            "manifest_id": _stable_id("candidate-universe", identity),
            "market": "CN",
            "universe_date": universe_date,
            "universe_version": universe_version,
            "security_types": policy.supported_security_types,
            "security_count": len(records),
            "ordered_symbols": [item[0] for item in records],
            "ordered_security_types": [item[1] for item in records],
            "ordered_source_refs": [item[2] for item in records],
            "ordered_security_hashes": [item[3] for item in records],
            "source_hash": source_hash,
            "created_at": now,
        }
        payload["universe_hash"] = recommendation_hash(
            payload, exclude={"manifest_id", "universe_hash", "created_at", "schema_version"}
        )
        manifest = CandidateUniverseManifest.model_validate(payload)
        existing = clean_document(
            await self.db["ag_candidate_universe_manifests"].find_one(
                {"manifest_id": manifest.manifest_id}
            )
        )
        if existing:
            stored = CandidateUniverseManifest.model_validate(existing)
            if stored.universe_hash != manifest.universe_hash:
                raise RecommendationIntegrityConflict("candidate universe manifest changed content")
            return stored
        if execute:
            await self.db["ag_candidate_universe_manifests"].insert_one(
                model_document(manifest)
            )
        return manifest

    async def _load_global_scan_inputs(
        self, *, user_id: str, trade_date: date
    ) -> dict[str, Any]:
        normalization_version = str(
            recommendation_data_contract()["normalization_version"]
        )
        regime_rows = [
            clean_document(row)
            for row in await self.db["ag_regime_results"].find({}).to_list(length=None)
            if (_as_date(row.get("trade_date")) or date.min) <= trade_date
        ]
        benchmark_rows = [
            clean_document(row)
            for row in await self.db["stock_daily_quotes"].find(
                {
                    "symbol": "000300",
                    "market": "CN",
                    "period": "daily",
                    "normalization_version": normalization_version,
                }
            ).to_list(length=None)
            if (_quote_date(row) or date.max) <= trade_date
        ]
        benchmark_rows.sort(key=lambda row: _quote_date(row) or date.min)
        candidates = [
            clean_document(row)
            for row in await self.db["ag_candidates"].find(
                {"user_id": str(user_id), "status": {"$ne": CandidateStatus.REMOVED.value}}
            ).to_list(length=None)
        ]
        account_ids: set[str] = set()
        for collection in ("ag_paper_accounts", "paper_accounts"):
            account_ids.update(
                str(row.get("account_id") or row.get("_id") or "")
                for row in await self.db[collection].find(
                    {"user_id": str(user_id)}
                ).to_list(length=None)
                if row.get("account_id") or row.get("_id")
            )
        positions = []
        for collection in ("ag_paper_positions", "paper_positions"):
            owner_filters: list[dict[str, Any]] = [{"user_id": str(user_id)}]
            if account_ids:
                owner_filters.append({"account_id": {"$in": sorted(account_ids)}})
            positions.extend(
                clean_document(row)
                for row in await self.db[collection].find(
                    {"$or": owner_filters, "quantity": {"$gt": 0}}
                ).to_list(length=None)
            )
        orders = []
        for collection in ("ag_paper_orders", "paper_orders"):
            orders.extend(
                clean_document(row)
                for row in await self.db[collection].find(
                    {"user_id": str(user_id)}
                ).to_list(length=None)
                if str(row.get("status") or "").upper() not in _TERMINAL_ORDER_STATUSES
            )
        active_plans = [
            clean_document(row)
            for row in await self.db["analysis_reports"].find(
                {"user_id": str(user_id)}
            ).to_list(length=None)
            if (row.get("normal_trade_plan") or {}).get("status") == "PROPOSE_TRADE"
        ]
        pending_labels = await self.db["ag_eval_horizon_labels"].find(
            {"status": "PENDING"}
        ).to_list(length=None)
        subject_ids = sorted(
            {str(row.get("subject_id")) for row in pending_labels if row.get("subject_id")}
        )
        pending_subjects = (
            await self.db["ag_eval_subjects"].find(
                {"subject_id": {"$in": subject_ids}, "user_id": str(user_id)}
            ).to_list(length=None)
            if subject_ids
            else []
        )
        calendar = sorted(
            {
                item
                for row in await self.db["trading_calendar"].find({}).to_list(length=None)
                if str(row.get("market") or "CN").upper() == "CN"
                and row.get("is_open") is True
                and (item := _as_date(
                    row.get("trade_date") or row.get("session_date") or row.get("date")
                ))
                is not None
            }
        )
        reviews = [
            clean_document(row)
            for row in await self.db["ag_candidate_recommendation_review_events"].find(
                {"user_id": str(user_id)}
            ).to_list(length=None)
        ]
        recommendations = [
            clean_document(row)
            for row in await self.db["ag_candidate_recommendations"].find(
                {"user_id": str(user_id)}
            ).to_list(length=None)
        ]
        return {
            "regime_rows": regime_rows,
            "benchmark_rows": benchmark_rows,
            "candidates": candidates,
            "positions": positions,
            "orders": orders,
            "active_plans": active_plans,
            "pending_subjects": [clean_document(row) for row in pending_subjects],
            "calendar": calendar,
            "reviews": reviews,
            "recommendations": recommendations,
        }

    async def _load_symbol_scan_inputs(
        self,
        *,
        trade_date: date,
        history_start: date,
        symbols: list[str],
    ) -> dict[str, Any]:
        symbol_query = {"symbol": {"$in": symbols}}
        contract = recommendation_data_contract()
        normalization_version = str(contract["normalization_version"])
        daily_rows = [
            clean_document(row)
            for row in await self.db["stock_daily_quotes"].find(
                {
                    **symbol_query,
                    "normalization_version": normalization_version,
                    "trade_date": {
                        "$gte": mongo_date(history_start),
                        "$lte": mongo_date(trade_date),
                    },
                }
            ).to_list(length=None)
            if _quote_mode(row) == "QFQ"
            and (row_date := _quote_date(row)) is not None
            and history_start <= row_date <= trade_date
        ]
        market_rows = [
            clean_document(row)
            for row in await self.db["market_quotes"].find(symbol_query).to_list(length=None)
            if _quote_date(row) == trade_date
        ]
        status_rows = [
            clean_document(row)
            for row in await self.db["ag_security_trading_statuses"].find(
                {**symbol_query, "market": "CN"}
            ).to_list(length=None)
            if _quote_date(row) == trade_date
        ]
        quality_rows = [
            clean_document(row)
            for row in await self.db[
                "ag_recommendation_data_quality_reports"
            ].find(
                {
                    **symbol_query,
                    "schema_version": str(contract["contract_version"]),
                }
            ).to_list(length=None)
            if _quote_date(row) == trade_date
        ]
        factor_rows = [
            clean_document(row)
            for row in await self.db["ag_factor_results"].find(symbol_query).to_list(length=None)
            if (_as_date(row.get("trade_date")) or date.min) <= trade_date
        ]
        proposal_rows = [
            clean_document(row)
            for row in await self.db["ag_quant_proposals"].find(symbol_query).to_list(length=None)
            if (_as_date(row.get("trade_date")) or date.min) <= trade_date
        ]
        return {
            "daily_rows": daily_rows,
            "market_rows": market_rows,
            "status_rows": status_rows,
            "quality_rows": quality_rows,
            "factor_rows": factor_rows,
            "proposal_rows": proposal_rows,
        }

    async def _load_scan_inputs(
        self,
        *,
        user_id: str,
        trade_date: date,
        symbols: list[str],
    ) -> dict[str, Any]:
        global_inputs = await self._load_global_scan_inputs(
            user_id=user_id, trade_date=trade_date
        )
        eligible_dates = [item for item in global_inputs["calendar"] if item <= trade_date]
        history_start = (
            eligible_dates[-61] if len(eligible_dates) >= 61 else eligible_dates[0]
        )
        symbol_inputs = await self._load_symbol_scan_inputs(
            trade_date=trade_date,
            history_start=history_start,
            symbols=symbols,
        )
        return {**global_inputs, **symbol_inputs}

    @staticmethod
    def _group_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        grouped: dict[str, Any] = {}
        for key in ("daily_rows", "factor_rows", "proposal_rows"):
            values: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in inputs[key]:
                values[str(row.get("symbol") or row.get("code") or "")].append(row)
            grouped[key] = values
        for key in ("market_rows", "quality_rows"):
            values = {}
            ordering_field = "checked_at" if key == "quality_rows" else "created_at"
            for row in sorted(
                inputs[key], key=lambda item: str(item.get(ordering_field) or "")
            ):
                symbol = str(row.get("symbol") or row.get("code") or "")
                if symbol:
                    values[symbol] = row
            grouped[key] = values
        statuses: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in inputs["status_rows"]:
            symbol = str(row.get("symbol") or row.get("code") or "")
            if symbol:
                statuses[symbol].append(row)
        grouped["status_rows"] = {}
        for symbol, rows in statuses.items():
            expected_id = str(
                (grouped["quality_rows"].get(symbol) or {}).get("trading_status_id")
                or ""
            )
            chosen = next(
                (
                    row
                    for row in rows
                    if expected_id
                    and str(row.get("trading_status_id") or "") == expected_id
                ),
                None,
            )
            if chosen is None:
                chosen = max(
                    rows,
                    key=lambda item: (
                        str(item.get("calculation_status") or "") == "READY",
                        str(item.get("collected_at") or ""),
                    ),
                )
            grouped["status_rows"][symbol] = chosen
        snapshot_to_regime = {
            str(row.get("snapshot_id")): row for row in inputs["regime_rows"]
        }
        grouped["regime_by_snapshot"] = snapshot_to_regime
        grouped["benchmark_rows"] = inputs.get("benchmark_rows", [])
        grouped["recommendation_factor_by_symbol"] = inputs.get(
            "recommendation_factor_by_symbol", {}
        )
        grouped["candidate_symbols"] = {
            str(row.get("symbol") or row.get("code")) for row in inputs["candidates"]
        }
        grouped["position_symbols"] = {
            str(row.get("symbol") or row.get("code")) for row in inputs["positions"]
        }
        grouped["order_symbols"] = {
            str(row.get("symbol") or row.get("code")) for row in inputs["orders"]
        }
        grouped["plan_symbols"] = {
            str(
                (row.get("normal_trade_plan") or {}).get("symbol")
                or row.get("stock_symbol")
                or ""
            )
            for row in inputs["active_plans"]
        }
        grouped["evaluation_symbols"] = {
            str(row.get("symbol") or "") for row in inputs["pending_subjects"]
        }
        grouped["calendar"] = inputs["calendar"]
        grouped["recommendations"] = inputs["recommendations"]
        grouped["review_by_recommendation"] = {
            str(row.get("recommendation_id")): row
            for row in sorted(inputs["reviews"], key=lambda item: item.get("created_at") or datetime.min)
        }
        return grouped

    @staticmethod
    def _listing_sessions(listing_date: date | None, trade_date: date, calendar: list[date]) -> int:
        if listing_date is None:
            return 0
        return sum(listing_date <= item <= trade_date for item in calendar)

    def _eligibility(
        self,
        *,
        run_id: str,
        symbol: str,
        security: dict[str, Any],
        trade_date: date,
        policy: CandidateRecommendationPolicy,
        grouped: dict[str, Any],
        now: datetime,
    ) -> CandidateEligibilityResult:
        reasons: list[str] = []
        name = str(security.get("name") or symbol)
        listing_status = str(
            security.get("listing_status") or security.get("status") or ""
        ).upper()
        if any(token in listing_status for token in ("DELIST", "退市", "TERMINATED")):
            reasons.append("DELISTED")
        if "退市整理" in name or "退" == name[:1]:
            reasons.append("DELISTING_PERIOD")
        is_st = "ST" in name.upper()
        if is_st and not policy.allow_st:
            reasons.append("ST_NOT_ALLOWED")
        listing_date = _as_date(security.get("list_date") or security.get("listing_date"))
        if listing_date is None:
            reasons.append("LISTING_DATE_MISSING")
        elif self._listing_sessions(listing_date, trade_date, grouped["calendar"]) < policy.minimum_listing_sessions:
            reasons.append("LISTING_HISTORY_INSUFFICIENT")

        rows = sorted(
            grouped["daily_rows"].get(symbol, []),
            key=lambda row: _quote_date(row) or date.min,
        )
        exact = rows[-1] if rows and _quote_date(rows[-1]) == trade_date else None
        market_quote = grouped["market_rows"].get(symbol)
        status = grouped["status_rows"].get(symbol)
        if len(rows) < policy.minimum_data_history:
            reasons.append("PRICE_HISTORY_INSUFFICIENT")
        if exact is None and market_quote is None:
            reasons.append("TRADE_DATE_QUOTE_MISSING")
        if status is None or str(status.get("calculation_status") or "") != "READY":
            reasons.append("TRADING_STATUS_NOT_READY")
        elif status.get("is_suspended") is True:
            reasons.append("SUSPENDED")

        quality = grouped["quality_rows"].get(symbol)
        quality_status = str((quality or {}).get("status") or "NOT_AVAILABLE").upper()
        if quality_status == "FAIL":
            reasons.append("DATA_QUALITY_FAILED")
        if quality_status == "NOT_AVAILABLE":
            reasons.append("DATA_QUALITY_NOT_AVAILABLE")

        lookback = rows[-policy.liquidity_lookback_sessions :]
        amounts = [_decimal(row.get("amount")) for row in lookback if row.get("amount") is not None]
        average_amount = (
            sum(amounts, Decimal("0")) / Decimal(len(amounts)) if amounts else None
        )
        if average_amount is None or average_amount < policy.minimum_average_amount:
            reasons.append("LOW_LIQUIDITY")
        zero_volume = sum(_decimal(row.get("volume")) <= 0 for row in lookback)
        if zero_volume > policy.maximum_zero_volume_sessions:
            reasons.append("LONG_NO_TRADE")
        invalid_price = False
        for row in lookback:
            open_price = _decimal(row.get("adjusted_open") or row.get("open"))
            high = _decimal(row.get("adjusted_high") or row.get("high"))
            low = _decimal(row.get("adjusted_low") or row.get("low"))
            close = _decimal(row.get("adjusted_close") or row.get("close"))
            if min(open_price, high, low, close) <= 0 or high < max(open_price, close, low) or low > min(open_price, close, high):
                invalid_price = True
                break
        if invalid_price:
            reasons.append("PRICE_DATA_ANOMALY")

        for code, values in (
            ("ALREADY_IN_CANDIDATE_POOL", grouped["candidate_symbols"]),
            ("POSITION_REQUIRES_MONITORING", grouped["position_symbols"]),
            ("UNFINISHED_ORDER", grouped["order_symbols"]),
            ("ACTIVE_TRADE_PLAN", grouped["plan_symbols"]),
            ("PENDING_EVALUATION", grouped["evaluation_symbols"]),
        ):
            if symbol in values:
                reasons.append(code)
        reasons = sorted(set(reasons))
        primary_reason = next(
            (code for code in _FILTER_PRIORITY if code in reasons),
            reasons[0] if reasons else None,
        )
        evidence_refs = sorted(
            {
                value
                for value in (
                    _quote_ref(exact or {}),
                    str((status or {}).get("ref_id") or ""),
                    str((quality or {}).get("quality_report_id") or ""),
                )
                if value
            }
        )
        input_payload = {
            "symbol": symbol,
            "trade_date": trade_date,
            "security_hash": recommendation_hash(
                {
                    "name": name,
                    "listing_status": listing_status,
                    "listing_date": listing_date,
                    "security_type": security["_recommendation_security_type"],
                }
            ),
            "quote_hashes": [str(row.get("content_hash") or recommendation_hash(row)) for row in lookback],
            "status_hash": str((status or {}).get("content_hash") or ""),
            "quality_hash": str((quality or {}).get("immutable_hash") or ""),
            "policy_version": policy.eligibility_policy_version,
        }
        input_hash = recommendation_hash(input_payload)
        output_payload = {
            "eligible": not reasons,
            "filter_reason_codes": reasons,
            "primary_filter_reason": primary_reason,
            "data_quality_status": quality_status,
            "history_count": len(rows),
            "required_history_days": policy.minimum_data_history,
            "data_version": str((quality or {}).get("data_version") or "NOT_AVAILABLE"),
            "average_amount": average_amount,
            "evidence_refs": evidence_refs,
        }
        output_hash = recommendation_hash(output_payload)
        return CandidateEligibilityResult(
            eligibility_result_id=_stable_id("candidate-eligibility", f"{run_id}:{symbol}"),
            recommendation_run_id=run_id,
            symbol=symbol,
            market="CN",
            trade_date=trade_date,
            security_type=security["_recommendation_security_type"],
            eligible=not reasons,
            filter_reason_codes=reasons,
            primary_filter_reason=primary_reason,
            required_history_days=policy.minimum_data_history,
            available_history_days=len(rows),
            data_version=str((quality or {}).get("data_version") or "NOT_AVAILABLE"),
            data_quality_status=(
                quality_status if quality_status in {"PASS", "WARN", "FAIL"} else "NOT_AVAILABLE"
            ),
            history_count=len(rows),
            average_amount=_money(average_amount) if average_amount is not None else None,
            policy_version=policy.eligibility_policy_version,
            evidence_refs=evidence_refs,
            input_hash=input_hash,
            output_hash=output_hash,
            created_at=now,
            schema_version=RECOMMENDATION_ELIGIBILITY_SCHEMA_VERSION,
        )

    @staticmethod
    def _latest_factor_set(symbol: str, grouped: dict[str, Any], trade_date: date) -> list[dict[str, Any]]:
        rows = grouped["factor_rows"].get(symbol, [])
        if not rows:
            return []
        dates = [_as_date(row.get("trade_date")) for row in rows]
        latest_date = max((item for item in dates if item is not None and item <= trade_date), default=None)
        if latest_date is None:
            return []
        dated = [row for row in rows if _as_date(row.get("trade_date")) == latest_date]
        snapshot_counts = Counter(str(row.get("snapshot_id") or "") for row in dated)
        snapshot_id = max(snapshot_counts, key=lambda item: (snapshot_counts[item], item))
        return sorted(
            [row for row in dated if str(row.get("snapshot_id") or "") == snapshot_id],
            key=lambda row: str(row.get("factor_id") or ""),
        )

    @staticmethod
    def _mean_score(rows: Iterable[dict[str, Any]], group: str) -> Decimal | None:
        values = [
            _decimal(row.get("normalized_score"))
            for row in rows
            if str(row.get("group") or "") == group and row.get("normalized_score") is not None
        ]
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else None

    @classmethod
    def _factor_set_supports_recommendation_scoring(
        cls, rows: list[dict[str, Any]]
    ) -> bool:
        if not rows:
            return False
        required_groups = ("TREND", "MOMENTUM", "LIQUIDITY")
        if any(cls._mean_score(rows, group) is None for group in required_groups):
            return False
        return any(
            str(row.get("factor_id") or "").startswith("relative_strength_")
            and row.get("normalized_score") is not None
            for row in rows
        )

    def _score(
        self,
        *,
        user_id: str,
        symbol: str,
        security: dict[str, Any],
        eligibility: CandidateEligibilityResult,
        trade_date: date,
        policy: CandidateRecommendationPolicy,
        grouped: dict[str, Any],
        run_id: str,
        expires_at: datetime,
        now: datetime,
    ) -> tuple[CandidateRecommendationScoreResult | None, CandidateRecommendation | None]:
        factors = self._latest_factor_set(symbol, grouped, trade_date)
        recommendation_factor = grouped["recommendation_factor_by_symbol"].get(symbol)
        use_snapshot_factors = self._factor_set_supports_recommendation_scoring(factors)
        if not use_snapshot_factors and recommendation_factor is None:
            return None, None
        snapshot_id = str(factors[0].get("snapshot_id") or "") if factors else ""
        if use_snapshot_factors:
            factor_scores = {
                group: self._mean_score(factors, group)
                for group in (
                    "TREND",
                    "MOMENTUM",
                    "LIQUIDITY",
                    "VOLATILITY_RISK",
                    "EVENT_RISK",
                )
            }
            relative_values = [
                _decimal(row.get("normalized_score"))
                for row in factors
                if str(row.get("factor_id") or "").startswith("relative_strength_")
                and row.get("normalized_score") is not None
            ]
            relative = relative_values[0] if relative_values else None
        else:
            assert isinstance(recommendation_factor, RecommendationFactorEvidence)
            factor_scores = {
                group: recommendation_factor.group_scores.get(group)
                for group in (
                    "TREND",
                    "MOMENTUM",
                    "LIQUIDITY",
                    "VOLATILITY_RISK",
                    "EVENT_RISK",
                )
            }
            relative = recommendation_factor.normalized_scores.get(
                "relative_strength_hs300_20d_v1"
            )
        regime = grouped["regime_by_snapshot"].get(snapshot_id)
        proposals = sorted(
            grouped["proposal_rows"].get(symbol, []),
            key=lambda row: (_as_date(row.get("trade_date")) or date.min, str(row.get("created_at") or "")),
            reverse=True,
        )
        proposal = next((row for row in proposals if str(row.get("snapshot_id")) == snapshot_id), None)
        required = [factor_scores["TREND"], factor_scores["MOMENTUM"], factor_scores["LIQUIDITY"], relative]
        if any(value is None for value in required):
            return None, None
        regime_score = {
            "TREND_UP": Decimal("100"),
            "RANGE_STRONG": Decimal("80"),
            "RANGE_WEAK": Decimal("55"),
            "TREND_DOWN": Decimal("20"),
            "EXTREME_RISK": Decimal("0"),
        }.get(str((regime or {}).get("regime") or ""), Decimal("0"))
        strategy_score = {
            "TRIGGERED": Decimal("100"),
            "WATCH": Decimal("70"),
            "REJECTED": Decimal("20"),
            "INSUFFICIENT_DATA": Decimal("0"),
            "INVALID_INPUT": Decimal("0"),
        }.get(str((proposal or {}).get("status") or ""), Decimal("0"))
        quality_score = {
            "PASS": Decimal("100"),
            "WARN": Decimal("70"),
        }.get(eligibility.data_quality_status, Decimal("0"))
        raw_components = {
            "DATA_QUALITY": quality_score,
            "LIQUIDITY": factor_scores["LIQUIDITY"] or Decimal("0"),
            "TREND": factor_scores["TREND"] or Decimal("0"),
            "MOMENTUM": factor_scores["MOMENTUM"] or Decimal("0"),
            "RELATIVE_STRENGTH": relative or Decimal("0"),
            "MARKET_REGIME": regime_score,
            "STRATEGY_SIGNAL": strategy_score,
        }
        score_components = {
            key: _money(value * policy.factor_weights[key])
            for key, value in raw_components.items()
        }
        daily = sorted(
            grouped["daily_rows"].get(symbol, []),
            key=lambda row: _quote_date(row) or date.min,
        )
        closes = [
            _decimal(row.get("adjusted_close") or row.get("close"))
            for row in daily[-60:]
        ]
        peak = Decimal("0")
        max_drawdown = Decimal("0")
        for close in closes:
            peak = max(peak, close)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - close) / peak * Decimal("100"))
        raw_risks = {
            "VOLATILITY_RISK": factor_scores["VOLATILITY_RISK"] or Decimal("0"),
            "EVENT_RISK": factor_scores["EVENT_RISK"] or Decimal("0"),
            "DRAWDOWN_RISK": min(Decimal("100"), max_drawdown * Decimal("5")),
        }
        risk_penalties = {
            key: _money(value * policy.risk_penalties[key])
            for key, value in raw_risks.items()
        }
        score = _money(
            max(
                Decimal("0"),
                min(
                    Decimal("100"),
                    sum(score_components.values(), Decimal("0"))
                    - sum(risk_penalties.values(), Decimal("0")),
                ),
            )
        )
        reason_codes: list[str] = []
        reasons: list[str] = []
        if raw_components["TREND"] >= 60:
            reason_codes.append("TREND_STRENGTH")
            reasons.append("近阶段趋势强度处于可研究区间")
        if raw_components["RELATIVE_STRENGTH"] >= 60:
            reason_codes.append("OUTPERFORMS_HS300")
            reasons.append("相对沪深300表现较强")
        if raw_components["LIQUIDITY"] >= 60:
            reason_codes.append("LIQUIDITY_READY")
            reasons.append("成交活跃度满足推荐策略要求")
        if regime_score >= 55:
            reason_codes.append("REGIME_COMPATIBLE")
            reasons.append("当前市场状态与既有策略研究方向相容")
        if strategy_score >= 70:
            reason_codes.append("STRATEGY_SIGNAL_PRESENT")
            reasons.append("既有确定性策略信号值得继续跟踪")
        if not reasons:
            reason_codes.append("COMPOSITE_SCORE_READY")
            reasons.append("多项确定性指标的综合评分达到推荐门槛")
        risk_codes: list[str] = []
        risk_reasons: list[str] = []
        if raw_risks["VOLATILITY_RISK"] >= 60:
            risk_codes.append("VOLATILITY_ELEVATED")
            risk_reasons.append("近期波动风险偏高")
        if raw_risks["EVENT_RISK"] >= 60:
            risk_codes.append("EVENT_EVIDENCE_RISK")
            risk_reasons.append("公告或事件证据存在风险扣分")
        if max_drawdown >= 10:
            risk_codes.append("DRAWDOWN_ELEVATED")
            risk_reasons.append("近期回撤风险偏高")
        if eligibility.data_quality_status != "PASS":
            risk_codes.append("DATA_QUALITY_WARNING")
            risk_reasons.append("部分数据质量证据需要人工复核")
        factor_refs = (
            sorted(str(row.get("result_id")) for row in factors if row.get("result_id"))
            if use_snapshot_factors
            else [recommendation_factor.evidence_id]
        )
        evidence_refs = sorted(
            set(eligibility.evidence_refs)
            | set(factor_refs)
            | {
                value
                for value in (
                    str((regime or {}).get("regime_result_id") or ""),
                    str((proposal or {}).get("proposal_id") or ""),
                )
                if value
            }
        )
        input_payload = {
            "eligibility_hash": eligibility.output_hash,
            "factor_input_hashes": (
                [str(row.get("input_hash") or "") for row in factors]
                if use_snapshot_factors
                else [recommendation_factor.input_hash]
            ),
            "regime_input_hash": str((regime or {}).get("input_hash") or ""),
            "proposal_input_hash": str((proposal or {}).get("input_hash") or ""),
            "policy_hash": policy.config_hash,
        }
        input_hash = recommendation_hash(input_payload)
        output_payload = {
            "score_components": score_components,
            "risk_penalties": risk_penalties,
            "recommendation_score": score,
            "reason_codes": reason_codes,
            "risk_codes": risk_codes,
        }
        output_hash = recommendation_hash(output_payload)
        score_result_payload = {
            "score_result_id": _stable_id(
                "candidate-recommendation-score", f"{run_id}:{symbol}:{input_hash}"
            ),
            "recommendation_run_id": run_id,
            "symbol": symbol,
            "trade_date": trade_date,
            "recommendation_score": score,
            "score_components": score_components,
            "risk_penalties": risk_penalties,
            "meets_threshold": score >= policy.minimum_recommendation_score,
            "minimum_recommendation_score": policy.minimum_recommendation_score,
            "evidence_refs": evidence_refs,
            "input_hash": input_hash,
            "output_hash": "0" * 64,
            "created_at": now,
        }
        score_result_payload["output_hash"] = recommendation_hash(
            score_result_payload,
            exclude={"output_hash", "created_at", "schema_version"},
        )
        score_result = CandidateRecommendationScoreResult.model_validate(
            score_result_payload
        )
        if score < policy.minimum_recommendation_score:
            return score_result, None
        recommendation_id = _stable_id(
            "candidate-recommendation", f"{run_id}:{symbol}:{input_hash}"
        )
        return score_result, CandidateRecommendation(
            recommendation_id=recommendation_id,
            recommendation_run_id=run_id,
            user_id=str(user_id),
            trade_date=trade_date,
            market="CN",
            symbol=symbol,
            security_name=str(security.get("name") or symbol),
            security_type=eligibility.security_type,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            recommendation_score=score,
            score_components=score_components,
            risk_penalties=risk_penalties,
            recommendation_reason_codes=reason_codes,
            recommendation_reasons=reasons,
            risk_reason_codes=risk_codes,
            risk_reasons=risk_reasons,
            data_quality_status=eligibility.data_quality_status,
            regime_type=str((regime or {}).get("regime") or "") or None,
            strategy_signal_status=str((proposal or {}).get("status") or "") or None,
            evidence_refs=evidence_refs,
            factor_result_refs=factor_refs,
            input_hash=input_hash,
            output_hash=output_hash,
            expires_at=expires_at,
            created_at=now,
        )

    @staticmethod
    def _expiry(trade_date: date, calendar: list[date], ttl: int) -> datetime:
        future = [item for item in calendar if item > trade_date]
        expiry_date = future[min(ttl, len(future)) - 1] if future else trade_date
        return datetime.combine(expiry_date, datetime_time(23, 59, 59))

    def _apply_review_governance(
        self,
        recommendation: CandidateRecommendation,
        *,
        grouped: dict[str, Any],
        policy: CandidateRecommendationPolicy,
        now: datetime,
    ) -> CandidateRecommendation | None:
        prior_rows = [
            row
            for row in grouped["recommendations"]
            if str(row.get("symbol") or "") == recommendation.symbol
            and str(row.get("user_id") or "") == recommendation.user_id
        ]
        if not prior_rows:
            return recommendation
        prior_row = max(
            prior_rows,
            key=lambda row: (
                _as_date(row.get("trade_date")) or date.min,
                str(row.get("created_at") or ""),
            ),
        )
        prior = CandidateRecommendation.model_validate(clean_document(prior_row))
        review = grouped["review_by_recommendation"].get(prior.recommendation_id)
        if prior.input_hash == recommendation.input_hash:
            return None
        if review and str(review.get("action")) in {"REJECTED", "IGNORED"}:
            cooldown = (
                policy.cooldown_days_rejected
                if str(review.get("action")) == "REJECTED"
                else policy.cooldown_days_ignored
            )
            elapsed = sum(
                prior.trade_date < item <= recommendation.trade_date
                for item in grouped["calendar"]
            )
            score_delta = abs(
                recommendation.recommendation_score - prior.recommendation_score
            )
            material_change = (
                score_delta >= policy.score_change_breaks_cooldown
                or recommendation.regime_type != prior.regime_type
                or recommendation.strategy_signal_status
                != prior.strategy_signal_status
            )
            if elapsed <= cooldown and not material_change:
                return None
        if review and str(review.get("action")) == "ACCEPTED":
            return None
        output_hash = recommendation_hash(
            {
                "base_output_hash": recommendation.output_hash,
                "supersedes_recommendation_id": prior.recommendation_id,
            }
        )
        return recommendation.model_copy(
            update={
                "supersedes_recommendation_id": prior.recommendation_id,
                "output_hash": output_hash,
            }
        )

    async def _record_superseded(
        self, recommendation: CandidateRecommendation, *, now: datetime
    ) -> None:
        prior_id = recommendation.supersedes_recommendation_id
        if not prior_id:
            return
        existing = await self._review_for(prior_id)
        if existing:
            return
        identity = f"{prior_id}:SYSTEM:SUPERSEDED:{recommendation.recommendation_id}"
        payload = {
            "review_event_id": _stable_id("candidate-recommendation-review", identity),
            "recommendation_id": prior_id,
            "user_id": recommendation.user_id,
            "action": "SUPERSEDED",
            "operator_user_id": "SYSTEM",
            "candidate_id": None,
            "review_note": f"superseded by {recommendation.recommendation_id}",
            "trace_id": None,
            "created_at": now,
        }
        payload["event_hash"] = recommendation_hash(
            payload, exclude={"event_hash", "created_at", "schema_version"}
        )
        event = CandidateRecommendationReviewEvent.model_validate(payload)
        try:
            await self.db["ag_candidate_recommendation_review_events"].insert_one(
                model_document(event)
            )
        except DuplicateKeyError:
            stored = await self._review_for(prior_id)
            if not stored or stored.event_hash != event.event_hash:
                raise RecommendationIntegrityConflict(
                    "recommendation supersession identity conflict"
                )

    async def _create_only_many(
        self,
        collection_name: str,
        items: list[Any],
        *,
        id_field: str,
        hash_field: str,
    ) -> None:
        if not items:
            return
        collection = self.db[collection_name]
        identifiers = [getattr(item, id_field) for item in items]
        existing_rows = await collection.find(
            {id_field: {"$in": identifiers}}
        ).to_list(length=None)
        existing = {str(row[id_field]): clean_document(row) for row in existing_rows}
        missing = []
        for item in items:
            stored = existing.get(str(getattr(item, id_field)))
            if stored:
                if str(stored.get(hash_field)) != str(getattr(item, hash_field)):
                    raise RecommendationIntegrityConflict(
                        f"{collection_name} identity changed immutable content"
                    )
            else:
                missing.append(model_document(item))
        if not missing:
            return
        if hasattr(collection, "bulk_write"):
            try:
                for offset in range(0, len(missing), 500):
                    await collection.bulk_write(
                        [InsertOne(row) for row in missing[offset : offset + 500]],
                        ordered=False,
                    )
            except BulkWriteError as exc:
                raise RecommendationIntegrityConflict(
                    f"create-only bulk write conflict in {collection_name}"
                ) from exc
        else:
            for row in missing:
                await collection.insert_one(row)

    async def run(
        self,
        *,
        user_id: str,
        trade_date: date | None = None,
        now: datetime | None = None,
    ) -> tuple[CandidateRecommendationRun, bool]:
        started = time.perf_counter()
        now = now or datetime.utcnow()
        trade_date = trade_date or await self.resolve_latest_trade_date()
        policy = await self.policy_registry.get_active()
        if not policy.enabled:
            raise RuntimeError("CANDIDATE_RECOMMENDATION_POLICY_DISABLED")
        universe = await self.build_universe_manifest(
            universe_date=trade_date,
            policy=policy,
            now=now,
        )
        securities = {
            str(row.get("code") or row.get("symbol")): row
            for row in await self._load_universe_rows()
        }
        data_service = RecommendationDataService(self.db)
        coverage = await data_service.prepare_coverage(
            universe=universe,
            securities=securities,
            policy=policy,
            trade_date=trade_date,
            execute=True,
            now=now,
        )
        global_inputs = await self._load_global_scan_inputs(
            user_id=str(user_id), trade_date=trade_date
        )
        user_constraints_hash = recommendation_hash(
            {
                key: global_inputs[key]
                for key in (
                    "candidates",
                    "positions",
                    "orders",
                    "active_plans",
                    "pending_subjects",
                )
            }
        )
        data_version = (
            f"{_CANDIDATE_INPUT_CONTRACT_VERSION}:{coverage.coverage_hash[:24]}:"
            f"{user_constraints_hash[:16]}"
        )
        identity = (
            f"{user_id}:{trade_date.isoformat()}:{universe.universe_version}:"
            f"{policy.policy_version}:{data_version}"
        )
        run_id = _stable_id("candidate-recommendation-run", identity)
        existing_run = clean_document(
            await self.db["ag_candidate_recommendation_runs"].find_one(
                {"recommendation_run_id": run_id}
            )
        )
        if existing_run:
            return CandidateRecommendationRun.model_validate(existing_run), False
        model_calls_before = await self.db["ag_model_runs"].count_documents({})
        eligible_dates = [
            item for item in global_inputs["calendar"] if item <= trade_date
        ]
        history_start = eligible_dates[-policy.minimum_data_history]
        expires_at = self._expiry(
            trade_date,
            global_inputs["calendar"],
            policy.recommendation_ttl_days,
        )
        eligibility: list[CandidateEligibilityResult] = []
        score_results: list[CandidateRecommendationScoreResult] = []
        candidates_above_threshold: list[CandidateRecommendation] = []
        failed_symbols: list[str] = []
        batch_size = int(data_service.contract["batch_size"])
        for offset in range(0, len(universe.ordered_symbols), batch_size):
            symbols = universe.ordered_symbols[offset : offset + batch_size]
            symbol_inputs = await self._load_symbol_scan_inputs(
                trade_date=trade_date,
                history_start=history_start,
                symbols=symbols,
            )
            grouped = self._group_inputs({**global_inputs, **symbol_inputs})
            batch_eligibility = [
                self._eligibility(
                    run_id=run_id,
                    symbol=symbol,
                    security=securities[symbol],
                    trade_date=trade_date,
                    policy=policy,
                    grouped=grouped,
                    now=now,
                )
                for symbol in symbols
            ]
            await self._create_only_many(
                "ag_candidate_eligibility_results",
                batch_eligibility,
                id_field="eligibility_result_id",
                hash_field="output_hash",
            )
            eligibility.extend(batch_eligibility)
            factor_evidences: list[RecommendationFactorEvidence] = []
            for result in batch_eligibility:
                factors = self._latest_factor_set(result.symbol, grouped, trade_date)
                if not result.eligible or self._factor_set_supports_recommendation_scoring(
                    factors
                ):
                    continue
                evidence = data_service.build_factor_evidence(
                    symbol=result.symbol,
                    trade_date=trade_date,
                    price_rows=grouped["daily_rows"].get(result.symbol, []),
                    benchmark_rows=global_inputs["benchmark_rows"],
                    now=now,
                )
                if evidence is not None:
                    factor_evidences.append(evidence)
            grouped["recommendation_factor_by_symbol"].update(
                await data_service.persist_factor_evidence_many(factor_evidences)
            )
            for result in batch_eligibility:
                if not result.eligible:
                    continue
                try:
                    score_result, recommendation = self._score(
                        user_id=str(user_id),
                        symbol=result.symbol,
                        security=securities[result.symbol],
                        eligibility=result,
                        trade_date=trade_date,
                        policy=policy,
                        grouped=grouped,
                        run_id=run_id,
                        expires_at=expires_at,
                        now=now,
                    )
                except Exception:
                    failed_symbols.append(result.symbol)
                    continue
                if score_result is not None:
                    score_results.append(score_result)
                if recommendation is not None:
                    governed = self._apply_review_governance(
                        recommendation,
                        grouped=grouped,
                        policy=policy,
                        now=now,
                    )
                    if governed is not None:
                        candidates_above_threshold.append(governed)
        await self._create_only_many(
            "ag_candidate_recommendation_score_results",
            score_results,
            id_field="score_result_id",
            hash_field="output_hash",
        )
        candidates_above_threshold.sort(
            key=lambda item: (-item.recommendation_score, item.trade_date, item.symbol)
        )
        selected = candidates_above_threshold[: policy.daily_result_limit]
        await self._create_only_many(
            "ag_candidate_recommendations",
            selected,
            id_field="recommendation_id",
            hash_field="output_hash",
        )
        for recommendation in selected:
            await self._record_superseded(recommendation, now=now)
        evaluations = [self._evaluation_for(item, now=now) for item in selected]
        await self._create_only_many(
            "ag_candidate_recommendation_evaluations",
            evaluations,
            id_field="evaluation_id",
            hash_field="output_hash",
        )
        model_calls_after = await self.db["ag_model_runs"].count_documents({})
        reason_counts = Counter(
            code for item in eligibility for code in item.filter_reason_codes
        )
        input_hash = recommendation_hash(
            {
                "identity": identity,
                "policy_hash": policy.config_hash,
                "universe_hash": universe.universe_hash,
                "coverage_hash": coverage.coverage_hash,
                "eligibility_hashes": [item.output_hash for item in eligibility],
            }
        )
        output_hash = recommendation_hash(
            {
                "recommendation_ids": [item.recommendation_id for item in selected],
                "recommendation_hashes": [item.output_hash for item in selected],
                "score_result_hashes": [item.output_hash for item in score_results],
                "failed_symbols": failed_symbols,
            }
        )
        completed = datetime.utcnow()
        run = CandidateRecommendationRun(
            recommendation_run_id=run_id,
            user_id=str(user_id),
            trade_date=trade_date,
            universe_manifest_id=universe.manifest_id,
            universe_version=universe.universe_version,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            data_version=data_version,
            total_securities=len(eligibility),
            eligible_securities=sum(item.eligible for item in eligibility),
            scored_securities=len(score_results),
            recommended_securities=len(selected),
            filtered_reason_counts=dict(sorted(reason_counts.items())),
            failed_symbols=sorted(failed_symbols),
            status="PARTIAL" if failed_symbols else "SUCCESS",
            model_call_count_before=model_calls_before,
            model_call_count_after=model_calls_after,
            started_at=now,
            completed_at=completed,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            input_hash=input_hash,
            output_hash=output_hash,
        )
        try:
            await self.db["ag_candidate_recommendation_runs"].insert_one(model_document(run))
        except DuplicateKeyError:
            stored = clean_document(
                await self.db["ag_candidate_recommendation_runs"].find_one(
                    {"recommendation_run_id": run_id}
                )
            )
            if not stored or str(stored.get("output_hash")) != run.output_hash:
                raise RecommendationIntegrityConflict("recommendation run identity conflict")
            return CandidateRecommendationRun.model_validate(stored), False
        return run, True

    @staticmethod
    def _evaluation_for(
        recommendation: CandidateRecommendation, *, now: datetime
    ) -> CandidateRecommendationEvaluation:
        horizons = {
            horizon: {
                "status": "PENDING",
                "forward_return": None,
                "relative_hs300_return": None,
                "relative_industry_return": None,
                "mfe": None,
                "mae": None,
            }
            for horizon in ("1D", "5D", "10D", "20D")
        }
        payload = {
            "recommendation_id": recommendation.recommendation_id,
            "user_id": recommendation.user_id,
            "symbol": recommendation.symbol,
            "trade_date": recommendation.trade_date,
            "policy_version": recommendation.policy_version,
            "status": "PENDING",
            "horizon_results": horizons,
            "accepted_into_candidate_pool": False,
            "later_strategy_triggered": False,
            "later_valid_trade_plan": False,
            "input_hash": recommendation.input_hash,
        }
        payload["output_hash"] = recommendation_hash(payload)
        return CandidateRecommendationEvaluation(
            evaluation_id=_stable_id(
                "candidate-recommendation-evaluation", recommendation.recommendation_id
            ),
            created_at=now,
            updated_at=now,
            **payload,
        )

    async def _get_recommendation_for_user(
        self, recommendation_id: str, user_id: str
    ) -> CandidateRecommendation:
        row = clean_document(
            await self.db["ag_candidate_recommendations"].find_one(
                {"recommendation_id": recommendation_id, "user_id": str(user_id)}
            )
        )
        if not row:
            raise LookupError("candidate recommendation not found")
        return CandidateRecommendation.model_validate(row)

    async def _review_for(self, recommendation_id: str) -> CandidateRecommendationReviewEvent | None:
        row = clean_document(
            await self.db["ag_candidate_recommendation_review_events"].find_one(
                {"recommendation_id": recommendation_id}, sort=[("created_at", -1)]
            )
        )
        return CandidateRecommendationReviewEvent.model_validate(row) if row else None

    async def effective_status(
        self, recommendation: CandidateRecommendation, *, now: datetime | None = None
    ) -> tuple[str, CandidateRecommendationReviewEvent | None]:
        review = await self._review_for(recommendation.recommendation_id)
        if review:
            return _STATUS_BY_ACTION[review.action], review
        if recommendation.expires_at < (now or datetime.utcnow()):
            return "EXPIRED", None
        return "PENDING_REVIEW", None

    async def list_recommendations(
        self,
        *,
        user_id: str,
        status: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        rows = await self.db["ag_candidate_recommendations"].find(
            {"user_id": str(user_id)}
        ).sort([("trade_date", -1), ("recommendation_score", -1)]).to_list(length=None)
        result = []
        for row in rows:
            item = CandidateRecommendation.model_validate(clean_document(row))
            effective, review = await self.effective_status(item)
            if status and effective != status:
                continue
            payload = item.model_dump(mode="json")
            payload.update(
                {
                    "status": effective,
                    "reviewed_at": review.created_at.isoformat() if review else None,
                    "review_note": review.review_note if review else None,
                    "candidate_id": review.candidate_id if review else None,
                }
            )
            result.append(payload)
        return result[skip : skip + limit]

    async def get_recommendation_detail(
        self, *, recommendation_id: str, user_id: str
    ) -> dict[str, Any]:
        recommendation = await self._get_recommendation_for_user(
            recommendation_id, user_id
        )
        status, review = await self.effective_status(recommendation)
        run = clean_document(
            await self.db["ag_candidate_recommendation_runs"].find_one(
                {"recommendation_run_id": recommendation.recommendation_run_id}
            )
        )
        eligibility = clean_document(
            await self.db["ag_candidate_eligibility_results"].find_one(
                {
                    "recommendation_run_id": recommendation.recommendation_run_id,
                    "symbol": recommendation.symbol,
                }
            )
        )
        evaluation = clean_document(
            await self.db["ag_candidate_recommendation_evaluations"].find_one(
                {"recommendation_id": recommendation.recommendation_id}
            )
        )
        return {
            **recommendation.model_dump(mode="json"),
            "status": status,
            "review": review.model_dump(mode="json") if review else None,
            "run": run,
            "eligibility": eligibility,
            "evaluation": evaluation,
        }

    async def list_runs(
        self, *, user_id: str, admin: bool = False, limit: int = 100
    ) -> list[CandidateRecommendationRun]:
        query = {} if admin else {"user_id": str(user_id)}
        rows = await self.db["ag_candidate_recommendation_runs"].find(query).sort(
            "completed_at", -1
        ).limit(limit).to_list(length=limit)
        return [CandidateRecommendationRun.model_validate(clean_document(row)) for row in rows]

    async def get_run(
        self, *, run_id: str, user_id: str, admin: bool = False
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"recommendation_run_id": run_id}
        if not admin:
            query["user_id"] = str(user_id)
        row = clean_document(
            await self.db["ag_candidate_recommendation_runs"].find_one(query)
        )
        if not row:
            raise LookupError("candidate recommendation run not found")
        run = CandidateRecommendationRun.model_validate(row)
        return {
            **run.model_dump(mode="json"),
            "eligibility": [
                clean_document(item)
                for item in await self.db["ag_candidate_eligibility_results"].find(
                    {"recommendation_run_id": run_id}
                ).to_list(length=None)
            ],
        }

    async def review(
        self,
        *,
        recommendation_id: str,
        user_id: str,
        action: str,
        review_note: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[CandidateRecommendationReviewEvent, bool]:
        action = action.upper()
        if action not in {"ACCEPTED", "REJECTED", "IGNORED"}:
            raise ValueError("unsupported recommendation review action")
        recommendation = await self._get_recommendation_for_user(
            recommendation_id, user_id
        )
        existing = await self._review_for(recommendation_id)
        if existing:
            if existing.action == action and existing.user_id == str(user_id):
                return existing, False
            raise RecommendationReviewConflict("recommendation already has a review decision")
        if recommendation.expires_at < datetime.utcnow():
            raise RecommendationReviewConflict("expired recommendation cannot be reviewed")
        candidate_id = None
        if action == "ACCEPTED":
            policy = await self.policy_registry.get_active()
            current = await CandidatePoolService(self.db).get_by_identity(
                str(user_id), recommendation.market, recommendation.symbol
            )
            if current is None:
                active_count = await self.db["ag_candidates"].count_documents(
                    {"user_id": str(user_id), "status": {"$ne": CandidateStatus.REMOVED.value}}
                )
                if active_count >= policy.candidate_pool_soft_limit:
                    raise CandidatePoolLimitReached(
                        "候选池已达到软上限，请先整理候选池"
                    )
            candidate = await CandidatePoolService(self.db).upsert_source(
                user_id=str(user_id),
                symbol=recommendation.symbol,
                market=recommendation.market,
                source=CandidateSource.SYSTEM_RECOMMENDED_CONFIRMED,
                name=recommendation.security_name,
                priority=min(100, max(0, int(recommendation.recommendation_score))),
                trace_id=trace_id,
                reason="user explicitly accepted governed candidate recommendation",
                recommendation_id=recommendation.recommendation_id,
                recommendation_run_id=recommendation.recommendation_run_id,
                recommendation_score=float(recommendation.recommendation_score),
                recommendation_trade_date=recommendation.trade_date,
                recommendation_reason_summary="；".join(
                    recommendation.recommendation_reasons[:2]
                ),
            )
            candidate_id = candidate.candidate_id
        identity = f"{recommendation_id}:{user_id}:{action}"
        payload = {
            "review_event_id": _stable_id("candidate-recommendation-review", identity),
            "recommendation_id": recommendation_id,
            "user_id": str(user_id),
            "action": action,
            "operator_user_id": str(user_id),
            "candidate_id": candidate_id,
            "review_note": review_note,
            "trace_id": trace_id,
            "created_at": datetime.utcnow(),
        }
        payload["event_hash"] = recommendation_hash(
            payload, exclude={"event_hash", "created_at", "schema_version"}
        )
        event = CandidateRecommendationReviewEvent.model_validate(payload)
        try:
            await self.db["ag_candidate_recommendation_review_events"].insert_one(
                model_document(event)
            )
        except DuplicateKeyError:
            stored = await self._review_for(recommendation_id)
            if stored and stored.event_hash == event.event_hash:
                return stored, False
            raise RecommendationIntegrityConflict("recommendation review identity conflict")
        if candidate_id:
            await self._mark_evaluation_accepted(recommendation_id)
        return event, True

    async def _mark_evaluation_accepted(self, recommendation_id: str) -> None:
        row = clean_document(
            await self.db["ag_candidate_recommendation_evaluations"].find_one(
                {"recommendation_id": recommendation_id}
            )
        )
        if not row or row.get("accepted_into_candidate_pool") is True:
            return
        row["accepted_into_candidate_pool"] = True
        row["updated_at"] = datetime.utcnow()
        row["output_hash"] = recommendation_hash(
            row,
            exclude={"evaluation_id", "output_hash", "created_at", "updated_at", "schema_version"},
        )
        evaluation = CandidateRecommendationEvaluation.model_validate(row)
        await self.db["ag_candidate_recommendation_evaluations"].replace_one(
            {"evaluation_id": evaluation.evaluation_id}, model_document(evaluation)
        )

    async def batch_review(
        self,
        *,
        recommendation_ids: list[str],
        user_id: str,
        action: str,
        review_note: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        unique = list(dict.fromkeys(recommendation_ids))
        if len(unique) > 50:
            raise ValueError("batch recommendation review is limited to 50 items")
        results = []
        for recommendation_id in unique:
            event, created = await self.review(
                recommendation_id=recommendation_id,
                user_id=str(user_id),
                action=action,
                review_note=review_note,
                trace_id=trace_id,
            )
            results.append(
                {
                    "recommendation_id": recommendation_id,
                    "action": event.action,
                    "created": created,
                    "candidate_id": event.candidate_id,
                }
            )
        return {"items": results, "processed": len(results)}

    async def metrics(self) -> dict[str, Any]:
        latest_run = clean_document(
            await self.db["ag_candidate_recommendation_runs"].find_one(
                {}, sort=[("completed_at", -1)]
            )
        )
        recommendations = await self.db["ag_candidate_recommendations"].find({}).to_list(length=None)
        reviews = await self.db["ag_candidate_recommendation_review_events"].find({}).to_list(length=None)
        counts = Counter(str(row.get("action")) for row in reviews)
        reviewed_ids = {str(row.get("recommendation_id")) for row in reviews}
        pending = sum(
            str(row.get("recommendation_id")) not in reviewed_ids
            and (row.get("expires_at") or datetime.min) >= datetime.utcnow()
            for row in recommendations
        )
        source_security_count = await self.db["stock_basic_info"].count_documents({})
        security_count = (
            int(latest_run["total_securities"])
            if latest_run and latest_run.get("total_securities") is not None
            else source_security_count
        )
        quote_count = await self.db["market_quotes"].count_documents({})
        open_calendar_count = await self.db["trading_calendar"].count_documents(
            {"is_open": True}
        )
        policy = await self.policy_registry.get_active(persist_if_missing=False)
        coverage = await RecommendationDataService(self.db).latest_coverage()
        score_rows = (
            await self.db["ag_candidate_recommendation_score_results"].find(
                {"recommendation_run_id": str(latest_run.get("recommendation_run_id"))}
            ).to_list(length=None)
            if latest_run
            else []
        )
        scores = sorted(
            (_decimal(row.get("recommendation_score")) for row in score_rows),
            reverse=True,
        )
        runtime_ready = bool(
            source_security_count and quote_count and open_calendar_count and policy.enabled
        )
        return {
            "recommendation_ready": runtime_ready,
            "recommendation_runtime_ready": runtime_ready,
            "recommendation_data_ready": bool(
                coverage and coverage.recommendation_data_ready
            ),
            "auto_candidate_accept": False,
            "security_count": security_count,
            "eligible_count": int((latest_run or {}).get("eligible_securities") or 0),
            "today_recommendation_count": int((latest_run or {}).get("recommended_securities") or 0),
            "pending_review_count": pending,
            "accepted_count": counts["ACCEPTED"],
            "rejected_count": counts["REJECTED"],
            "ignored_count": counts["IGNORED"],
            "last_run_status": (latest_run or {}).get("status") or "NOT_RUN",
            "last_success_at": (latest_run or {}).get("completed_at"),
            "last_duration_ms": int((latest_run or {}).get("duration_ms") or 0),
            "failed_symbol_count": len((latest_run or {}).get("failed_symbols") or []),
            "policy_version": (latest_run or {}).get("policy_version")
            or policy.policy_version,
            "coverage_status": coverage.status if coverage else "NOT_READY",
            "coverage_percentage": (
                coverage.coverage_percentage if coverage else Decimal("0")
            ),
            "history_ready_count": (
                coverage.adjusted_history_ready_count if coverage else 0
            ),
            "trade_status_ready_count": (
                coverage.trade_status_ready_count if coverage else 0
            ),
            "data_quality_pass_count": (
                coverage.data_quality_pass_count if coverage else 0
            ),
            "coverage_failed_symbol_count": (
                coverage.failed_symbol_count if coverage else security_count
            ),
            "blocking_reason_counts": (
                coverage.blocking_reason_counts if coverage else {}
            ),
            "last_sync_at": (
                coverage.sync_completed_at if coverage else None
            ),
            "top_score": scores[0] if scores else None,
            "score_distribution": {
                "gte_70": sum(value >= Decimal("70") for value in scores),
                "55_to_70": sum(
                    Decimal("55") <= value < Decimal("70") for value in scores
                ),
                "below_55": sum(value < Decimal("55") for value in scores),
            },
        }

    async def coverage(self, *, trade_date: date | None = None) -> dict[str, Any]:
        coverage = await RecommendationDataService(self.db).latest_coverage(
            trade_date=trade_date
        )
        if coverage is None:
            return {
                "status": "NOT_READY",
                "recommendation_data_ready": False,
                "blocking_reason_counts": {"COVERAGE_NOT_BUILT": 1},
            }
        return coverage.model_dump(mode="json")

    async def refresh_evaluations(
        self, *, as_of_trade_date: date
    ) -> dict[str, int]:
        """Mature recommendation labels without touching account/equity metrics."""

        rows = await self.db["ag_candidate_recommendation_evaluations"].find(
            {"status": {"$in": ["PENDING", "PARTIAL", "INSUFFICIENT_DATA"]}}
        ).to_list(length=None)
        counts = {"calculated": 0, "partial": 0, "insufficient": 0}
        for raw in rows:
            evaluation = CandidateRecommendationEvaluation.model_validate(
                clean_document(raw)
            )
            security_quotes = [
                clean_document(row)
                for row in await self.db["stock_daily_quotes"].find(
                    {"symbol": evaluation.symbol}
                ).to_list(length=None)
                if _quote_mode(row) == "QFQ"
                and (item_date := _quote_date(row)) is not None
                and evaluation.trade_date <= item_date <= as_of_trade_date
            ]
            benchmark_quotes = [
                clean_document(row)
                for row in await self.db["stock_daily_quotes"].find(
                    {"symbol": "000300"}
                ).to_list(length=None)
                if _quote_mode(row) == "INDEX_UNADJUSTED_EQUIVALENT"
                and (item_date := _quote_date(row)) is not None
                and evaluation.trade_date <= item_date <= as_of_trade_date
            ]
            security_quotes.sort(key=lambda row: _quote_date(row) or date.min)
            benchmark_quotes.sort(key=lambda row: _quote_date(row) or date.min)
            security_by_date = {_quote_date(row): row for row in security_quotes}
            benchmark_by_date = {_quote_date(row): row for row in benchmark_quotes}
            anchor = security_by_date.get(evaluation.trade_date)
            benchmark_anchor = benchmark_by_date.get(evaluation.trade_date)
            future_dates = sorted(
                item for item in security_by_date if item and item > evaluation.trade_date
            )
            horizon_results: dict[str, dict[str, Any]] = {}
            for horizon, sessions in (("1D", 1), ("5D", 5), ("10D", 10), ("20D", 20)):
                if (
                    anchor is None
                    or len(future_dates) < sessions
                    or future_dates[sessions - 1] > as_of_trade_date
                ):
                    horizon_results[horizon] = {
                        "status": "PENDING",
                        "forward_return": None,
                        "relative_hs300_return": None,
                        "relative_industry_return": None,
                        "industry_status": "SOURCE_UNAVAILABLE",
                        "mfe": None,
                        "mae": None,
                    }
                    continue
                end_date = future_dates[sessions - 1]
                end = security_by_date[end_date]
                anchor_close = _decimal(anchor.get("adjusted_close") or anchor.get("close"))
                end_close = _decimal(end.get("adjusted_close") or end.get("close"))
                window = [security_by_date[item] for item in future_dates[:sessions]]
                highs = [_decimal(item.get("adjusted_high") or item.get("high")) for item in window]
                lows = [_decimal(item.get("adjusted_low") or item.get("low")) for item in window]
                forward = (end_close / anchor_close - 1) if anchor_close > 0 else None
                benchmark_end = benchmark_by_date.get(end_date)
                benchmark_return = None
                if benchmark_anchor and benchmark_end:
                    base = _decimal(benchmark_anchor.get("close"))
                    final = _decimal(benchmark_end.get("close"))
                    if base > 0:
                        benchmark_return = final / base - 1
                horizon_results[horizon] = {
                    "status": "CALCULATED",
                    "end_trade_date": end_date.isoformat(),
                    "forward_return": str(_money(forward)) if forward is not None else None,
                    "relative_hs300_return": (
                        str(_money(forward - benchmark_return))
                        if forward is not None and benchmark_return is not None
                        else None
                    ),
                    "relative_industry_return": None,
                    "industry_status": "SOURCE_UNAVAILABLE",
                    "mfe": (
                        str(_money(max(highs) / anchor_close - 1))
                        if highs and anchor_close > 0
                        else None
                    ),
                    "mae": (
                        str(_money(min(lows) / anchor_close - 1))
                        if lows and anchor_close > 0
                        else None
                    ),
                }
            calculated = sum(
                item["status"] == "CALCULATED" for item in horizon_results.values()
            )
            status = (
                "CALCULATED"
                if calculated == 4
                else ("PARTIAL" if calculated else "INSUFFICIENT_DATA")
            )
            accepted = bool(
                await self.db["ag_candidate_recommendation_review_events"].find_one(
                    {
                        "recommendation_id": evaluation.recommendation_id,
                        "action": "ACCEPTED",
                    }
                )
            )
            later_proposal = bool(
                await self.db["ag_quant_proposals"].find_one(
                    {
                        "symbol": evaluation.symbol,
                        "trade_date": {"$gt": mongo_date(evaluation.trade_date)},
                        "status": "TRIGGERED",
                    }
                )
            )
            payload = evaluation.model_dump(mode="python")
            payload.update(
                {
                    "status": status,
                    "horizon_results": horizon_results,
                    "accepted_into_candidate_pool": accepted,
                    "later_strategy_triggered": later_proposal,
                    "later_valid_trade_plan": bool(
                        await self.db["analysis_reports"].find_one(
                            {
                                "user_id": evaluation.user_id,
                                "stock_symbol": evaluation.symbol,
                                "normal_trade_plan.status": "PROPOSE_TRADE",
                            }
                        )
                    ),
                    "updated_at": datetime.utcnow(),
                }
            )
            payload["output_hash"] = recommendation_hash(
                payload,
                exclude={
                    "evaluation_id",
                    "output_hash",
                    "created_at",
                    "updated_at",
                    "schema_version",
                },
            )
            updated = CandidateRecommendationEvaluation.model_validate(payload)
            await self.db["ag_candidate_recommendation_evaluations"].replace_one(
                {"evaluation_id": evaluation.evaluation_id}, model_document(updated)
            )
            counts[
                "calculated"
                if status == "CALCULATED"
                else ("partial" if status == "PARTIAL" else "insufficient")
            ] += 1
        return counts
