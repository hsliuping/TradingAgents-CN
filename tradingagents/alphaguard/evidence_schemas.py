"""Data quality and immutable evidence contracts for AlphaGuard PR-003."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .instruments import Market, normalize_instrument


DATA_QUALITY_SCHEMA_VERSION = "data-quality-report-v1"
EVIDENCE_SNAPSHOT_SCHEMA_VERSION = "evidence-snapshot-v1"
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
    data_quality: DataQualityReport
    raw_refs: dict[str, list[str]]
    factor_version_set: dict[str, str] = Field(default_factory=dict)
    strategy_version: str | None = None
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
        return self
