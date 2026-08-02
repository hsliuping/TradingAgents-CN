"""Immutable EvidenceSnapshot service and analysis preflight validation."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.core.database import get_mongo_db
from tradingagents.alphaguard.evidence_schemas import (
    ALPHAGUARD_CODE_VERSION,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
    DataQualityReport,
    EvidenceSnapshot,
)
from tradingagents.alphaguard.instruments import normalize_instrument

from .data_quality_gate import DataQualityGate
from .paper_storage import to_mongo_value


logger = logging.getLogger(__name__)


class DataQualityBlockedError(ValueError):
    def __init__(self, report: DataQualityReport):
        self.report = report
        super().__init__("EvidenceSnapshot blocked by DataQuality FAIL")


class SnapshotValidationError(ValueError):
    pass


def _clean_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    cleaned = dict(document)
    cleaned.pop("_id", None)
    return cleaned


def _bson_stable_value(value: Any) -> Any:
    """Normalize datetimes to MongoDB's millisecond storage precision."""

    if isinstance(value, BaseModel):
        return _bson_stable_value(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return value.replace(microsecond=(value.microsecond // 1000) * 1000)
    if isinstance(value, dict):
        return {
            str(key): _bson_stable_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_bson_stable_value(item) for item in value]
    return value


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        v2_optional_fields = {
            "market_context_hash",
            "market_context_window_manifest_id",
            "market_context_window_manifest_hash",
            "benchmark_price_window_manifest_id",
            "benchmark_price_window_manifest_hash",
            "required_benchmark_count",
            "actual_benchmark_count",
            "decision_evidence_pack_manifest_id",
            "decision_evidence_pack_manifest_hash",
            "evidence_completeness_matrix",
            "evidence_contract_status",
            "run_mode",
            "source_trade_date",
            "evidence_contract_version",
            "reprocess_reason",
            "reprocess_input_hash",
            "original_realtime_run",
            "automated_execution_allowed",
        }
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in {"_id", "immutable_hash"}
            and not (key == "champion_version_refs" and not item)
            and not (key in v2_optional_fields and item is None)
        }
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_value(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def canonical_snapshot_json(snapshot: EvidenceSnapshot | dict[str, Any]) -> str:
    canonical = _canonical_value(snapshot)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def calculate_immutable_hash(
    snapshot: EvidenceSnapshot | dict[str, Any],
) -> str:
    return hashlib.sha256(
        canonical_snapshot_json(snapshot).encode("utf-8")
    ).hexdigest()


def _snapshot_document(snapshot: EvidenceSnapshot) -> dict[str, Any]:
    return to_mongo_value(
        _bson_stable_value(snapshot.model_dump(mode="python"))
    )


class EvidenceSnapshotService:
    """Create-only EvidenceSnapshot persistence boundary."""

    def __init__(
        self,
        db=None,
        gate: DataQualityGate | None = None,
        *,
        snapshot_collection: str = "ag_evidence_snapshots",
        quality_collection: str = "ag_data_quality_reports",
        enable_shadow_hook: bool = True,
    ):
        self._db = db
        self.gate = gate or DataQualityGate()
        self.snapshot_collection = snapshot_collection
        self.quality_collection = quality_collection
        self.enable_shadow_hook = enable_shadow_hook

    @property
    def db(self):
        return self._db if self._db is not None else get_mongo_db()

    async def create(
        self,
        *,
        user_id: str,
        payload: dict[str, Any],
    ) -> EvidenceSnapshot:
        data = dict(payload)
        internal_snapshot_id = data.pop("_internal_snapshot_id", None)
        if internal_snapshot_id is not None:
            deterministic_modes = {
                "PRODUCTION_REPROCESS",
                "EVIDENCE_CONTRACT_VALIDATION",
            }
            if data.get("run_mode") not in deterministic_modes:
                raise ValueError(
                    "deterministic internal snapshot identity is restricted "
                    "to non-executable evidence repair/validation modes"
                )
            if (
                data.get("run_mode") == "EVIDENCE_CONTRACT_VALIDATION"
                and self.snapshot_collection == "ag_evidence_snapshots"
            ):
                raise ValueError(
                    "evidence-contract validation snapshot must use an "
                    "isolated collection"
                )
            if data.get("automated_execution_allowed") is not False:
                raise ValueError(
                    "deterministic validation snapshot must disable execution"
                )
            existing = await self.db[self.snapshot_collection].find_one(
                {"snapshot_id": str(internal_snapshot_id)}
            )
            if existing is not None:
                stored = EvidenceSnapshot.model_validate(
                    _clean_document(existing)
                )
                if (
                    not self.verify_integrity(stored)
                    or stored.run_mode != data.get("run_mode")
                    or stored.reprocess_input_hash
                    != data.get("reprocess_input_hash")
                ):
                    raise SnapshotValidationError(
                        "INTEGRITY_CONFLICT: deterministic reprocess "
                        "Snapshot identity changed"
                    )
                return stored
        if data.get("factor_version_set") or data.get("strategy_version"):
            from .factor_registry import FactorRegistry
            from .strategy_registry import STRATEGY_SET_VERSION, StrategyRegistry

            expected_factors = await FactorRegistry(self.db).get_version_set(
                require_registered=True
            )
            if data.get("factor_version_set") != expected_factors:
                raise ValueError(
                    "factor_version_set must match the registered factor-set-v1"
                )
            if data.get("strategy_version") != STRATEGY_SET_VERSION:
                raise ValueError(
                    f"strategy_version must be {STRATEGY_SET_VERSION}"
                )
            await StrategyRegistry(self.db).require_strategy_set()
        market, symbol = normalize_instrument(data["symbol"], data["market"])
        trade_date = data["trade_date"]
        if isinstance(trade_date, str):
            trade_date = date.fromisoformat(trade_date)
        schema_version = str(
            data.get("schema_version") or EVIDENCE_SNAPSHOT_SCHEMA_VERSION
        )
        required_source_counts = dict(
            data.pop("required_source_counts", {}) or {}
        )
        expected_manifest_hashes = dict(
            data.pop("expected_manifest_hashes", {}) or {}
        )
        if schema_version in {
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
        }:
            required_count = int(data.get("required_benchmark_count") or 0)
            required_source_counts["benchmark_prices"] = required_count
            required_source_counts["benchmark_price_window"] = 1
            required_source_counts["market_context_window"] = 1
            expected_manifest_hashes.update(
                {
                    "benchmark_price_window": str(
                        data.get("benchmark_price_window_manifest_hash") or ""
                    ),
                    "market_context_window": str(
                        data.get("market_context_window_manifest_hash") or ""
                    ),
                }
            )
            if schema_version == EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3:
                required_source_counts["decision_evidence_pack"] = 1
                expected_manifest_hashes["decision_evidence_pack"] = str(
                    data.get("decision_evidence_pack_manifest_hash") or ""
                )
        report = await self.gate.evaluate(
            db=self.db,
            symbol=symbol,
            market=market,
            trade_date=trade_date,
            price_cutoff_at=data["price_cutoff_at"],
            news_cutoff_at=data["news_cutoff_at"],
            announcement_cutoff_at=data["announcement_cutoff_at"],
            raw_refs=data["raw_refs"],
            required_sources=data.pop("required_sources", None),
            required_source_counts=required_source_counts,
            expected_manifest_hashes=expected_manifest_hashes,
        )
        report = DataQualityReport.model_validate(
            _bson_stable_value(report.model_dump(mode="python"))
        )
        await self.db[self.quality_collection].insert_one(
            to_mongo_value(report.model_dump(mode="python"))
        )
        if report.status == "FAIL":
            raise DataQualityBlockedError(report)

        validation_mode = data.get("run_mode") == "EVIDENCE_CONTRACT_VALIDATION"
        champion_version_refs: dict[str, str] = (
            dict(data.get("champion_version_refs") or {})
            if validation_mode
            else {}
        )
        if data.get("factor_version_set") and data.get("strategy_version"):
            has_pr008_registry = (
                await self.db["ag_exp_champion_assignments"].find_one({})
                is not None
            )
            if has_pr008_registry and not validation_mode:
                from .champion_resolver import ChampionResolver

                champion_version_refs = (
                    await ChampionResolver(self.db).resolve_required_components(
                        market=market,
                        as_of_trade_date=trade_date,
                    )
                )

        snapshot_data = {
            "snapshot_id": str(internal_snapshot_id or uuid4()),
            "user_id": str(user_id),
            "analysis_id": data.get("analysis_id"),
            "symbol": symbol,
            "market": market,
            "trade_date": trade_date,
            "price_cutoff_at": data["price_cutoff_at"],
            "news_cutoff_at": data["news_cutoff_at"],
            "announcement_cutoff_at": data["announcement_cutoff_at"],
            "price_data_version": data["price_data_version"],
            "financial_data_version": data["financial_data_version"],
            "news_data_version": data["news_data_version"],
            "account_snapshot_id": data.get("account_snapshot_id"),
            "market_context_id": data.get("market_context_id"),
            "market_context_hash": data.get("market_context_hash"),
            "market_context_window_manifest_id": data.get(
                "market_context_window_manifest_id"
            ),
            "market_context_window_manifest_hash": data.get(
                "market_context_window_manifest_hash"
            ),
            "benchmark_price_window_manifest_id": data.get(
                "benchmark_price_window_manifest_id"
            ),
            "benchmark_price_window_manifest_hash": data.get(
                "benchmark_price_window_manifest_hash"
            ),
            "decision_evidence_pack_manifest_id": data.get(
                "decision_evidence_pack_manifest_id"
            ),
            "decision_evidence_pack_manifest_hash": data.get(
                "decision_evidence_pack_manifest_hash"
            ),
            "evidence_completeness_matrix": data.get(
                "evidence_completeness_matrix"
            ),
            "required_benchmark_count": data.get("required_benchmark_count"),
            "actual_benchmark_count": data.get("actual_benchmark_count"),
            "evidence_contract_status": data.get("evidence_contract_status"),
            "run_mode": data.get("run_mode"),
            "source_trade_date": data.get("source_trade_date"),
            "evidence_contract_version": data.get(
                "evidence_contract_version"
            ),
            "reprocess_reason": data.get("reprocess_reason"),
            "reprocess_input_hash": data.get("reprocess_input_hash"),
            "original_realtime_run": data.get("original_realtime_run"),
            "automated_execution_allowed": data.get(
                "automated_execution_allowed"
            ),
            "data_quality": report.model_dump(mode="python"),
            "raw_refs": data["raw_refs"],
            # Version selection is immutable and hashed before any PR-004
            # calculation. Empty/None remains a truthful legacy research mode.
            "factor_version_set": data.get("factor_version_set", {}),
            "strategy_version": data.get("strategy_version"),
            "champion_version_refs": champion_version_refs,
            "normal_model_version": data.get("normal_model_version"),
            "top_model_version": data.get("top_model_version"),
            "prompt_versions": data.get("prompt_versions", {}),
            "created_at": datetime.utcnow(),
            "schema_version": schema_version,
            "code_version": ALPHAGUARD_CODE_VERSION,
        }
        snapshot_data = _bson_stable_value(snapshot_data)
        # Hash the canonical Pydantic representation. Real snapshots contain
        # large reference sets whose input order is normalized by the schema;
        # hashing before validation would make the stored object fail its own
        # integrity check even though its evidence content is unchanged.
        snapshot_data["immutable_hash"] = "0" * 64
        normalized = EvidenceSnapshot.model_validate(snapshot_data)
        snapshot_data = normalized.model_dump(mode="python")
        snapshot_data["immutable_hash"] = calculate_immutable_hash(normalized)
        snapshot = EvidenceSnapshot.model_validate(snapshot_data)
        await self.db[self.snapshot_collection].insert_one(
            _snapshot_document(snapshot)
        )
        # PR-008 Shadow is best-effort and fully isolated.  A failure to enqueue
        # experiment work must never roll back or pause the production snapshot.
        if not self.enable_shadow_hook:
            return snapshot
        try:
            from app.services.alphaguard.experiment_task_service import (
                ExperimentTaskService,
            )

            active_shadows = await self.db["ag_exp_shadow_runs"].find(
                {"status": "ACTIVE"}
            ).to_list(length=None)
            task_service = ExperimentTaskService(self.db)
            for shadow in active_shadows:
                await task_service.enqueue(
                    "SHADOW_SNAPSHOT",
                    experiment_id=shadow["experiment_id"],
                    payload={
                        "shadow_run_id": shadow["shadow_run_id"],
                        "snapshot_id": snapshot.snapshot_id,
                    },
                    requested_by="evidence-snapshot-hook",
                    trade_date=snapshot.trade_date,
                )
        except Exception as exc:
            # The durable experiment reconciliation worker records/retries
            # experiment failures; production EvidenceSnapshot remains valid.
            try:
                from app.services.alphaguard.experiment_audit_service import (
                    ExperimentAuditService,
                )

                await ExperimentAuditService(self.db).record(
                    "EXPERIMENT_RUN_FAILED",
                    f"Shadow enqueue failed: {type(exc).__name__}",
                    user_id=str(user_id),
                    market=snapshot.market,
                    input_hash=snapshot.immutable_hash,
                )
            except Exception:
                logger.exception(
                    "PR-008 Shadow enqueue/audit failed without affecting "
                    "production EvidenceSnapshot %s",
                    snapshot.snapshot_id,
                )
        return snapshot

    async def get(
        self, snapshot_id: str, user_id: str | None = None
    ) -> EvidenceSnapshot | None:
        query: dict[str, Any] = {"snapshot_id": snapshot_id}
        if user_id is not None:
            query["user_id"] = str(user_id)
        document = await self.db[self.snapshot_collection].find_one(query)
        cleaned = _clean_document(document)
        if cleaned is None:
            return None
        try:
            return EvidenceSnapshot.model_validate(cleaned)
        except ValidationError as exc:
            raise SnapshotValidationError(
                "stored EvidenceSnapshot fails schema validation"
            ) from exc

    async def list(
        self,
        *,
        user_id: str,
        symbol: str | None = None,
        market: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceSnapshot]:
        query: dict[str, Any] = {"user_id": str(user_id)}
        if symbol:
            normalized_market, normalized_symbol = normalize_instrument(symbol, market)
            query.update(market=normalized_market, symbol=normalized_symbol)
        cursor = (
            self.db[self.snapshot_collection]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return [
            EvidenceSnapshot.model_validate(_clean_document(document))
            for document in await cursor.to_list(length=limit)
        ]

    @staticmethod
    def verify_integrity(snapshot: EvidenceSnapshot | dict[str, Any]) -> bool:
        try:
            model = (
                snapshot
                if isinstance(snapshot, EvidenceSnapshot)
                else EvidenceSnapshot.model_validate(_clean_document(snapshot))
            )
        except (ValidationError, TypeError):
            return False
        return calculate_immutable_hash(model) == model.immutable_hash

    async def verify_stored(
        self, snapshot_id: str, user_id: str | None = None
    ) -> bool:
        snapshot = await self.get(snapshot_id, user_id)
        if snapshot is None:
            raise LookupError("EvidenceSnapshot not found")
        return self.verify_integrity(snapshot)

    async def get_quality(
        self, snapshot_id: str, user_id: str | None = None
    ) -> DataQualityReport | None:
        snapshot = await self.get(snapshot_id, user_id)
        return snapshot.data_quality if snapshot else None

    async def validate_for_analysis(
        self,
        *,
        snapshot_id: str,
        user_id: str,
        symbol: str,
        market: str,
    ) -> dict[str, Any]:
        snapshot = await self.get(snapshot_id, user_id)
        if snapshot is None:
            raise SnapshotValidationError("snapshot_id does not exist for this user")
        if not self.verify_integrity(snapshot):
            raise SnapshotValidationError("EvidenceSnapshot immutable_hash mismatch")
        expected_market, expected_symbol = normalize_instrument(symbol, market)
        if snapshot.symbol != expected_symbol or snapshot.market != expected_market:
            raise SnapshotValidationError(
                "EvidenceSnapshot symbol/market does not match analysis request"
            )
        if snapshot.data_quality.status == "FAIL":
            raise SnapshotValidationError(
                "EvidenceSnapshot DataQuality FAIL blocks analysis"
            )
        return {
            "snapshot_id": snapshot.snapshot_id,
            "data_quality_status": snapshot.data_quality.status,
            "symbol": snapshot.symbol,
            "market": snapshot.market,
            "trade_date": snapshot.trade_date.isoformat(),
            "legacy_analysis": False,
            # PR-003 creates analysis provenance, not an execution permission.
            "automated_execution_allowed": False,
        }


def get_evidence_snapshot_service() -> EvidenceSnapshotService:
    return EvidenceSnapshotService()
