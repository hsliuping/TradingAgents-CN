"""Data quality and immutable evidence contracts for AlphaGuard PR-003."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .instruments import Market, normalize_instrument
from .decision_evidence_schemas import EvidenceCompletenessMatrix


DATA_QUALITY_SCHEMA_VERSION = "data-quality-report-v1"
EVIDENCE_SNAPSHOT_SCHEMA_VERSION = "evidence-snapshot-v1"
EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2 = "evidence-snapshot-v2"
EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3 = "evidence-snapshot-v3"
ALPHAGUARD_CODE_VERSION = "alphaguard-pr004-v1"


class EvidenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DataQualityReport(EvidenceSchema):
    quality_report_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    market: Market
    trade_date: date
    status: Literal["PASS", "WARN", "FAIL"]
    completeness_score: float = Field(ge=0, le=1)
    freshness_score: float = Field(ge=0, le=1)
    consistency_score: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    stale_sources: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    checked_at: datetime
    schema_version: str = DATA_QUALITY_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def normalize_identity(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("symbol") and data.get("market"):
            market, symbol = normalize_instrument(data["symbol"], data["market"])
            data["market"] = market
            data["symbol"] = symbol
        return data

    @field_validator(
        "missing_fields",
        "stale_sources",
        "anomalies",
        "blocking_reasons",
    )
    @classmethod
    def unique_messages(cls, values: list[str]) -> list[str]:
        return sorted({value for value in values if value})

    @model_validator(mode="after")
    def validate_status(self) -> "DataQualityReport":
        if self.status == "FAIL" and not self.blocking_reasons:
            raise ValueError("FAIL data quality requires blocking_reasons")
        if self.status != "FAIL" and self.blocking_reasons:
            raise ValueError("blocking_reasons require FAIL data quality status")
        return self


class EvidenceSnapshot(EvidenceSchema):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    snapshot_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    analysis_id: str | None = None
    symbol: str = Field(min_length=1)
    market: Market
    trade_date: date
    price_cutoff_at: datetime
    news_cutoff_at: datetime
    announcement_cutoff_at: datetime
    price_data_version: str = Field(min_length=1)
    financial_data_version: str = Field(min_length=1)
    news_data_version: str = Field(min_length=1)
    account_snapshot_id: str | None = None
    market_context_id: str | None = None
    # v2 locks the complete evidence-window identities and hashes.  These
    # remain optional solely so immutable v1 documents continue to parse and
    # verify without migration or hash changes.
    market_context_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    market_context_window_manifest_id: str | None = None
    market_context_window_manifest_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    benchmark_price_window_manifest_id: str | None = None
    benchmark_price_window_manifest_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    decision_evidence_pack_manifest_id: str | None = None
    decision_evidence_pack_manifest_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    evidence_completeness_matrix: EvidenceCompletenessMatrix | None = None
    required_benchmark_count: int | None = Field(default=None, ge=61)
    actual_benchmark_count: int | None = Field(default=None, ge=0)
    evidence_contract_status: Literal[
        "COMPLETE",
        "LEGACY_EVIDENCE_INCOMPLETE",
    ] | None = None
    # Explicit execution provenance for post-close production reprocessing.
    # Optional defaults preserve the exact validation and hash of immutable
    # v1/v2 records created before this contract was introduced.
    run_mode: Literal[
        "ACTUAL_PRODUCTION",
        "PRODUCTION_REPROCESS",
        "EVIDENCE_CONTRACT_VALIDATION",
        "RESEARCH_BACKFILL",
        "UI_DEMO",
    ] | None = None
    source_trade_date: date | None = None
    evidence_contract_version: str | None = None
    reprocess_reason: str | None = None
    reprocess_input_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    original_realtime_run: bool | None = None
    automated_execution_allowed: bool | None = None
    data_quality: DataQualityReport
    raw_refs: dict[str, list[str]]
    factor_version_set: dict[str, str] = Field(default_factory=dict)
    strategy_version: str | None = None
    # PR-008 server-resolved immutable component pointers.  Legacy snapshots
    # legitimately omit this map and retain their PR-004 version fields.
    champion_version_refs: dict[str, str] = Field(default_factory=dict)
    normal_model_version: str | None = None
    top_model_version: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EVIDENCE_SNAPSHOT_SCHEMA_VERSION
    code_version: str = ALPHAGUARD_CODE_VERSION

    @model_validator(mode="before")
    @classmethod
    def normalize_identity_and_refs(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("symbol") and data.get("market"):
            market, symbol = normalize_instrument(data["symbol"], data["market"])
            data["market"] = market
            data["symbol"] = symbol
        raw_refs = data.get("raw_refs")
        if isinstance(raw_refs, dict):
            data["raw_refs"] = {
                str(key): sorted({str(item) for item in items if str(item)})
                for key, items in raw_refs.items()
            }
        return data

    @model_validator(mode="after")
    def validate_snapshot(self) -> "EvidenceSnapshot":
        if self.data_quality.status == "FAIL":
            raise ValueError("FAIL data quality cannot be embedded in EvidenceSnapshot")
        if (
            self.data_quality.symbol != self.symbol
            or self.data_quality.market != self.market
            or self.data_quality.trade_date != self.trade_date
        ):
            raise ValueError("data quality identity must match EvidenceSnapshot")
        legacy_unversioned = not self.factor_version_set and self.strategy_version is None
        formal_quant = bool(self.factor_version_set) and bool(self.strategy_version)
        if not (legacy_unversioned or formal_quant):
            raise ValueError(
                "factor_version_set and strategy_version must be supplied together"
            )
        if any(
            not factor_id or not version or version.lower() == "latest"
            for factor_id, version in self.factor_version_set.items()
        ):
            raise ValueError("factor versions must use explicit non-latest identifiers")
        if self.strategy_version and self.strategy_version.lower() == "latest":
            raise ValueError("strategy_version must be explicit and not latest")
        if any(
            not slot_id
            or not version_ref
            or version_ref.strip().lower() == "latest"
            for slot_id, version_ref in self.champion_version_refs.items()
        ):
            raise ValueError(
                "Champion version refs must use explicit non-latest identifiers"
            )
        if self.schema_version in {
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
        }:
            required_v2 = (
                self.market_context_id,
                self.market_context_hash,
                self.market_context_window_manifest_id,
                self.market_context_window_manifest_hash,
                self.benchmark_price_window_manifest_id,
                self.benchmark_price_window_manifest_hash,
                self.required_benchmark_count,
                self.actual_benchmark_count,
            )
            if any(value is None for value in required_v2):
                raise ValueError(
                    "evidence-snapshot-v2 requires all evidence-window identities"
                )
            if self.evidence_contract_status != "COMPLETE":
                raise ValueError("evidence-snapshot-v2 requires COMPLETE contract")
            assert self.required_benchmark_count is not None
            assert self.actual_benchmark_count is not None
            if self.actual_benchmark_count < self.required_benchmark_count:
                raise ValueError("benchmark evidence window is incomplete")
            if len(self.raw_refs.get("benchmark_prices", [])) != (
                self.actual_benchmark_count
            ):
                raise ValueError(
                    "benchmark raw reference count does not match v2 contract"
                )
            expected_manifest_refs = {
                "market_context_window": (
                    f"market_context_window:"
                    f"{self.market_context_window_manifest_id}"
                ),
                "benchmark_price_window": (
                    f"benchmark_price_window:"
                    f"{self.benchmark_price_window_manifest_id}"
                ),
            }
            for category, reference in expected_manifest_refs.items():
                if self.raw_refs.get(category) != [reference]:
                    raise ValueError(
                        f"{category} reference does not match v2 contract"
                    )
            if self.schema_version == EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3:
                if (
                    not self.decision_evidence_pack_manifest_id
                    or not self.decision_evidence_pack_manifest_hash
                    or self.evidence_completeness_matrix is None
                ):
                    raise ValueError(
                        "evidence-snapshot-v3 requires Decision Evidence Pack identity"
                    )
                if any(
                    status not in {"COMPLETE", "NOT_APPLICABLE"}
                    for status in self.evidence_completeness_matrix.model_dump(
                        mode="python"
                    ).values()
                ):
                    raise ValueError(
                        "evidence-snapshot-v3 requires complete decision evidence"
                    )
                if self.raw_refs.get("decision_evidence_pack") != [
                    "decision_evidence_pack:"
                    f"{self.decision_evidence_pack_manifest_id}"
                ]:
                    raise ValueError(
                        "Decision Evidence Pack reference does not match v3 contract"
                    )
        elif self.schema_version != EVIDENCE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported EvidenceSnapshot schema: {self.schema_version}"
            )
        if self.run_mode == "PRODUCTION_REPROCESS":
            if self.schema_version != EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2:
                raise ValueError(
                    "PRODUCTION_REPROCESS requires EvidenceSnapshot v2"
                )
            if (
                self.source_trade_date != self.trade_date
                or self.evidence_contract_version != "evidence-contract-v2"
                or self.reprocess_reason != "EVIDENCE_CONTRACT_UPGRADE"
                or self.reprocess_input_hash is None
                or self.original_realtime_run is not False
                or self.automated_execution_allowed is not False
            ):
                raise ValueError(
                    "PRODUCTION_REPROCESS provenance is incomplete or executable"
                )
        return self
