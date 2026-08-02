"""Immutable Decision Evidence Pack contracts for PR-010 validation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .instruments import Market, normalize_instrument


DECISION_EVIDENCE_PACK_SCHEMA_VERSION = "decision-evidence-pack-v3"
DECISION_EVIDENCE_CALCULATION_VERSION = "decision-evidence-normalization-v2"

EvidenceCompletenessStatus = Literal[
    "COMPLETE",
    "PARTIAL",
    "MISSING",
    "NOT_APPLICABLE",
]
EvidenceSourceStatus = Literal["READY", "PARTIAL", "SOURCE_UNAVAILABLE"]


class DecisionEvidenceSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class EvidenceCategoryContract(DecisionEvidenceSchema):
    category: Literal[
        "financial_evidence",
        "cashflow_evidence",
        "dividend_evidence",
        "announcement_evidence",
    ]
    status: EvidenceCompletenessStatus
    source_status: EvidenceSourceStatus
    required_fields: list[str]
    available_fields: list[str]
    missing_fields: list[str]
    source_refs: list[str]
    source_hashes: list[str]
    source_versions: list[str]
    source_response_hashes: list[str]
    source_error_code: str | None = None
    category_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_category(self) -> "EvidenceCategoryContract":
        required = sorted(set(self.required_fields))
        available = sorted(set(self.available_fields))
        missing = sorted(set(self.missing_fields))
        if (
            self.required_fields != required
            or self.available_fields != available
            or self.missing_fields != missing
        ):
            raise ValueError("evidence field lists must be unique and ordered")
        if set(available) & set(missing):
            raise ValueError("available and missing evidence fields must be disjoint")
        if set(missing) != set(required) - set(available):
            raise ValueError("missing fields must equal required minus available fields")
        if len(self.source_refs) != len(self.source_hashes):
            raise ValueError("source reference and hash counts must match")
        if self.source_refs != sorted(set(self.source_refs)):
            raise ValueError("source references must be unique and ordered")
        if any(len(item) != 64 for item in self.source_hashes):
            raise ValueError("source hashes must be SHA-256 values")
        if any(len(item) != 64 for item in self.source_response_hashes):
            raise ValueError("source response hashes must be SHA-256 values")
        if self.status == "COMPLETE":
            if missing or self.source_status != "READY" or not self.source_refs:
                raise ValueError("COMPLETE evidence requires all fields and READY sources")
        elif self.status == "NOT_APPLICABLE":
            if missing or self.source_status != "READY":
                raise ValueError("NOT_APPLICABLE requires a successful source check")
        elif self.status == "MISSING" and available:
            raise ValueError("MISSING evidence cannot expose available required fields")
        if self.source_status == "SOURCE_UNAVAILABLE" and not self.source_error_code:
            raise ValueError("SOURCE_UNAVAILABLE requires source_error_code")
        return self


class EvidenceCompletenessMatrix(DecisionEvidenceSchema):
    financial_evidence: EvidenceCompletenessStatus
    cashflow_evidence: EvidenceCompletenessStatus
    dividend_evidence: EvidenceCompletenessStatus
    announcement_evidence: EvidenceCompletenessStatus


class DecisionEvidencePackManifest(DecisionEvidenceSchema):
    manifest_id: str = Field(min_length=1)
    ref_id: str = Field(min_length=1)
    market: Market
    symbol: str = Field(min_length=1)
    decision_time: datetime
    source_trade_date: date
    source_snapshot_id: str = Field(min_length=1)
    financial_evidence: EvidenceCategoryContract
    cashflow_evidence: EvidenceCategoryContract
    dividend_evidence: EvidenceCategoryContract
    announcement_evidence: EvidenceCategoryContract
    evidence_completeness_matrix: EvidenceCompletenessMatrix
    ordered_evidence_refs: list[str]
    ordered_evidence_hashes: list[str]
    provider_versions: dict[str, str]
    calculation_version: str = DECISION_EVIDENCE_CALCULATION_VERSION
    overall_status: EvidenceCompletenessStatus
    completeness_score: float = Field(ge=0, le=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    available_at: datetime
    created_at: datetime
    schema_version: str = DECISION_EVIDENCE_PACK_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def normalize_identity(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("symbol") and data.get("market"):
            market, symbol = normalize_instrument(data["symbol"], data["market"])
            data["market"] = market
            data["symbol"] = symbol
        return data

    @model_validator(mode="after")
    def validate_manifest(self) -> "DecisionEvidencePackManifest":
        if self.ref_id != self.manifest_id:
            raise ValueError("manifest ref_id must equal manifest_id")
        if self.source_trade_date != self.decision_time.date():
            raise ValueError("decision evidence date must match decision time")
        categories = {
            "financial_evidence": self.financial_evidence,
            "cashflow_evidence": self.cashflow_evidence,
            "dividend_evidence": self.dividend_evidence,
            "announcement_evidence": self.announcement_evidence,
        }
        matrix = self.evidence_completeness_matrix.model_dump(mode="python")
        if any(category.category != name for name, category in categories.items()):
            raise ValueError("evidence category identity mismatch")
        if matrix != {name: category.status for name, category in categories.items()}:
            raise ValueError("evidence completeness matrix does not match categories")
        ordered_pairs = sorted(
            {
                (reference, content_hash)
                for category in categories.values()
                for reference, content_hash in zip(
                    category.source_refs,
                    category.source_hashes,
                )
            }
        )
        if self.ordered_evidence_refs != [item[0] for item in ordered_pairs] or (
            self.ordered_evidence_hashes != [item[1] for item in ordered_pairs]
        ):
            raise ValueError("ordered evidence identities must match category sources")
        complete_count = sum(
            category.status in {"COMPLETE", "NOT_APPLICABLE"}
            for category in categories.values()
        )
        expected_score = round(complete_count / len(categories), 4)
        if self.completeness_score != expected_score:
            raise ValueError("evidence completeness score is inconsistent")
        expected_status = (
            "COMPLETE"
            if complete_count == len(categories)
            else "MISSING"
            if complete_count == 0
            else "PARTIAL"
        )
        if self.overall_status != expected_status:
            raise ValueError("overall evidence status is inconsistent")
        return self
