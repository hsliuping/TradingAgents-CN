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
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in {"_id", "immutable_hash"}
            and not (key == "champion_version_refs" and not item)
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

    def __init__(self, db=None, gate: DataQualityGate | None = None):
        self._db = db
        self.gate = gate or DataQualityGate()

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
        )
        report = DataQualityReport.model_validate(
            _bson_stable_value(report.model_dump(mode="python"))
        )
        await self.db["ag_data_quality_reports"].insert_one(
            to_mongo_value(report.model_dump(mode="python"))
        )
        if report.status == "FAIL":
            raise DataQualityBlockedError(report)

        champion_version_refs: dict[str, str] = {}
        if data.get("factor_version_set") and data.get("strategy_version"):
            has_pr008_registry = (
                await self.db["ag_exp_champion_assignments"].find_one({})
                is not None
            )
            if has_pr008_registry:
                from .champion_resolver import ChampionResolver

                champion_version_refs = (
                    await ChampionResolver(self.db).resolve_required_components(
                        market=market,
                        as_of_trade_date=trade_date,
                    )
                )

        snapshot_data = {
            "snapshot_id": str(uuid4()),
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
            "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
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
        await self.db["ag_evidence_snapshots"].insert_one(
            _snapshot_document(snapshot)
        )
        # PR-008 Shadow is best-effort and fully isolated.  A failure to enqueue
        # experiment work must never roll back or pause the production snapshot.
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
        document = await self.db["ag_evidence_snapshots"].find_one(query)
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
            self.db["ag_evidence_snapshots"]
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
