"""Create-only Decision Evidence Pack v3 persistence and readiness gate."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tradingagents.alphaguard.decision_evidence_schemas import (
    DECISION_EVIDENCE_CALCULATION_VERSION,
    DECISION_EVIDENCE_PACK_SCHEMA_VERSION,
    DecisionEvidencePackManifest,
    EvidenceCategoryContract,
    EvidenceCompletenessMatrix,
)
from tradingagents.alphaguard.instruments import normalize_instrument
from tradingagents.alphaguard.production_data_schemas import production_data_hash

from .decision_evidence_provider import (
    AKShareDecisionEvidenceProvider,
    DecisionEvidenceFetchResult,
    DecisionEvidenceProvider,
)
from .paper_storage import clean_document, model_document, to_mongo_value


FINANCIAL_REQUIRED_FIELDS = (
    "asset_liability_ratio",
    "deducted_net_profit",
    "gross_margin",
    "net_income",
    "net_profit",
    "net_profit_qoq",
    "net_profit_yoy",
    "revenue",
    "revenue_qoq",
    "revenue_yoy",
    "roe",
)
CASHFLOW_REQUIRED_FIELDS = (
    "free_cash_flow",
    "investing_cash_flow",
    "operating_cash_flow",
    "operating_cash_flow_to_net_income",
)
DIVIDEND_REQUIRED_FIELDS = (
    "ex_dividend_date",
    "plan_description",
    "published_at",
)
ANNOUNCEMENT_REQUIRED_FIELDS = (
    "announcement_category",
    "attachment_content_hash",
    "evidence_excerpt",
    "published_at",
    "title",
)


class DecisionEvidencePackError(RuntimeError):
    pass


class DecisionEvidencePackConflict(DecisionEvidencePackError):
    pass


def _stable_id(namespace: str, value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"alphaguard:{namespace}:{value}"))


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _summary(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    return "; ".join(
        f"{field}={record[field]}" for field in fields if _present(record.get(field))
    )


class DecisionEvidencePackService:
    COLLECTION = "ag_decision_evidence_pack_manifests"
    FINANCIAL_COLLECTION = "stock_financial_data"
    DIVIDEND_COLLECTION = "stock_corporate_actions"
    ANNOUNCEMENT_COLLECTION = "stock_announcements"

    def __init__(self, db):
        self.db = db

    @staticmethod
    def verify_integrity(manifest: DecisionEvidencePackManifest) -> bool:
        payload = manifest.model_dump(mode="python")
        stored_hash = payload.pop("manifest_hash")
        return production_data_hash(
            payload,
            exclude={"created_at"},
        ) == stored_hash

    @staticmethod
    def _source_document(
        *,
        namespace: str,
        reference_type: str,
        record: dict[str, Any],
        provider_version: str,
        collected_at: datetime,
        schema_version: str,
    ) -> tuple[str, dict[str, Any]]:
        source_record_id = str(record["source_record_id"])
        ref_id = _stable_id(namespace, source_record_id)
        business = {
            "ref_id": ref_id,
            **record,
            "provider_version": provider_version,
        }
        document = {
            **business,
            "available_at": record["published_at"],
            "collected_at": collected_at,
            "created_at": collected_at,
            "content_hash": production_data_hash(business),
            "schema_version": schema_version,
        }
        return f"{reference_type}:{ref_id}", document

    @classmethod
    def _documents(
        cls,
        result: DecisionEvidenceFetchResult,
        *,
        collected_at: datetime,
    ) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        provider_version = str(result.provider_versions.get("akshare") or "unknown")
        financial: list[tuple[str, dict[str, Any]]] = []
        cashflow: list[tuple[str, dict[str, Any]]] = []
        dividends: list[tuple[str, dict[str, Any]]] = []
        announcements: list[tuple[str, dict[str, Any]]] = []
        actions: list[tuple[str, dict[str, Any]]] = []
        for record in result.financial_records:
            value = dict(record)
            value["financial_summary"] = _summary(value, FINANCIAL_REQUIRED_FIELDS)
            value["cashflow_summary"] = _summary(value, CASHFLOW_REQUIRED_FIELDS)
            value["summary"] = (
                f"financial: {value['financial_summary']}; "
                f"cashflow: {value['cashflow_summary']}"
            )
            _, document = cls._source_document(
                namespace="decision-financial-v3",
                reference_type="decision_financial",
                record=value,
                provider_version=provider_version,
                collected_at=collected_at,
                schema_version="alphaguard-decision-financial-v3",
            )
            financial.append((f"decision_financial:{document['ref_id']}", document))
            cashflow.append((f"decision_cashflow:{document['ref_id']}", document))
        for record in result.announcement_records:
            reference, document = cls._source_document(
                namespace="decision-announcement-v3",
                reference_type="decision_announcement",
                record=dict(record),
                provider_version=provider_version,
                collected_at=collected_at,
                schema_version="alphaguard-decision-announcement-v3",
            )
            announcements.append((reference, document))
        for record in result.corporate_action_records:
            reference, document = cls._source_document(
                namespace="decision-corporate-action-v3",
                reference_type="decision_corporate_action",
                record=dict(record),
                provider_version=provider_version,
                collected_at=collected_at,
                schema_version="alphaguard-decision-corporate-action-v3",
            )
            actions.append((reference, document))
        for record in result.dividend_records:
            value = dict(record)
            value["summary"] = _summary(value, DIVIDEND_REQUIRED_FIELDS)
            reference, document = cls._source_document(
                namespace="decision-dividend-v3-v2",
                reference_type="decision_dividend",
                record=value,
                provider_version=provider_version,
                collected_at=collected_at,
                schema_version="alphaguard-decision-dividend-v3",
            )
            dividends.append((reference, document))
        return {
            "financial_evidence": financial,
            "cashflow_evidence": cashflow,
            "dividend_evidence": dividends + actions,
            "announcement_evidence": announcements,
            "corporate_actions": actions,
        }

    @staticmethod
    def _category(
        *,
        name: str,
        required_fields: tuple[str, ...],
        sources: list[tuple[str, dict[str, Any]]],
        source_status: str,
        source_response_hashes: list[str],
        source_error_code: str | None,
        not_applicable_when_empty: bool = False,
    ) -> EvidenceCategoryContract:
        required = sorted(required_fields)
        primary_documents = [item[1] for item in sources]
        available = sorted(
            field
            for field in required
            if any(_present(document.get(field)) for document in primary_documents)
        )
        missing = sorted(set(required) - set(available))
        if not sources and not_applicable_when_empty and source_status == "READY":
            required = []
            available = []
            missing = []
            status = "NOT_APPLICABLE"
        elif not available:
            status = "MISSING"
        elif not missing and source_status == "READY":
            status = "COMPLETE"
        else:
            status = "PARTIAL"
        pairs = sorted(
            (reference, str(document["content_hash"]))
            for reference, document in sources
        )
        payload = {
            "category": name,
            "status": status,
            "source_status": source_status,
            "required_fields": required,
            "available_fields": available,
            "missing_fields": missing,
            "source_refs": [item[0] for item in pairs],
            "source_hashes": [item[1] for item in pairs],
            "source_versions": sorted(
                {
                    str(document.get("data_version") or "unknown")
                    for _, document in sources
                }
            ),
            "source_response_hashes": sorted(set(source_response_hashes)),
            "source_error_code": source_error_code,
        }
        payload["category_hash"] = production_data_hash(payload)
        return EvidenceCategoryContract.model_validate(payload)

    @classmethod
    def _manifest(
        cls,
        *,
        symbol: str,
        decision_time: datetime,
        source_trade_date: date,
        source_snapshot_id: str,
        result: DecisionEvidenceFetchResult,
        documents: dict[str, list[tuple[str, dict[str, Any]]]],
        created_at: datetime,
    ) -> DecisionEvidencePackManifest:
        categories = {}
        for name, required_fields in (
            ("financial_evidence", FINANCIAL_REQUIRED_FIELDS),
            ("cashflow_evidence", CASHFLOW_REQUIRED_FIELDS),
            ("dividend_evidence", DIVIDEND_REQUIRED_FIELDS),
            ("announcement_evidence", ANNOUNCEMENT_REQUIRED_FIELDS),
        ):
            response_hashes = [
                result.source_response_hashes[key]
                for key in (
                    [name, "corporate_action_evidence"]
                    if name == "dividend_evidence"
                    else [name]
                )
                if result.source_response_hashes.get(key)
            ]
            source_status = str(result.source_statuses.get(name) or "SOURCE_UNAVAILABLE")
            source_error = result.source_errors.get(name)
            if name == "dividend_evidence":
                action_status = str(
                    result.source_statuses.get("corporate_action_evidence")
                    or "SOURCE_UNAVAILABLE"
                )
                if source_status != action_status:
                    source_status = "PARTIAL"
                elif action_status != "READY":
                    source_status = action_status
                source_error = source_error or result.source_errors.get(
                    "corporate_action_evidence"
                )
            categories[name] = cls._category(
                name=name,
                required_fields=required_fields,
                sources=documents[name],
                source_status=source_status,
                source_response_hashes=response_hashes,
                source_error_code=source_error,
                not_applicable_when_empty=name == "dividend_evidence",
            )
        matrix = EvidenceCompletenessMatrix(
            **{name: category.status for name, category in categories.items()}
        )
        pairs = sorted(
            {
                (reference, content_hash)
                for category in categories.values()
                for reference, content_hash in zip(
                    category.source_refs,
                    category.source_hashes,
                )
            }
        )
        complete_count = sum(
            category.status in {"COMPLETE", "NOT_APPLICABLE"}
            for category in categories.values()
        )
        overall_status = (
            "COMPLETE"
            if complete_count == len(categories)
            else "MISSING"
            if complete_count == 0
            else "PARTIAL"
        )
        source_payload = {
            "market": "CN",
            "symbol": symbol,
            "decision_time": decision_time,
            "source_trade_date": source_trade_date,
            "source_snapshot_id": source_snapshot_id,
            **categories,
            "evidence_completeness_matrix": matrix,
            "ordered_evidence_refs": [item[0] for item in pairs],
            "ordered_evidence_hashes": [item[1] for item in pairs],
            "provider_versions": dict(sorted(result.provider_versions.items())),
            "calculation_version": DECISION_EVIDENCE_CALCULATION_VERSION,
            "overall_status": overall_status,
            "completeness_score": round(complete_count / len(categories), 4),
        }
        source_hash = production_data_hash(source_payload)
        available_values = [
            document["available_at"]
            for source_documents in documents.values()
            for _, document in source_documents
            if document.get("available_at") is not None
        ]
        manifest_id = _stable_id(
            "decision-evidence-pack-v3",
            (
                f"CN:{symbol}:{source_trade_date.isoformat()}:"
                f"{decision_time.isoformat()}:{source_snapshot_id}:"
                f"{DECISION_EVIDENCE_CALCULATION_VERSION}"
            ),
        )
        payload = {
            "manifest_id": manifest_id,
            "ref_id": manifest_id,
            **source_payload,
            "source_hash": source_hash,
            "available_at": max(available_values, default=decision_time),
            "created_at": created_at,
            "schema_version": DECISION_EVIDENCE_PACK_SCHEMA_VERSION,
        }
        payload["manifest_hash"] = production_data_hash(
            payload,
            exclude={"created_at"},
        )
        return DecisionEvidencePackManifest.model_validate(payload)

    async def _check_documents(
        self,
        collection_name: str,
        documents: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        new: list[dict[str, Any]] = []
        reused = 0
        for document in documents:
            existing = clean_document(
                await self.db[collection_name].find_one(
                    {"ref_id": document["ref_id"]}
                )
            )
            if existing is None:
                new.append(document)
            elif existing.get("content_hash") == document["content_hash"]:
                reused += 1
            else:
                raise DecisionEvidencePackConflict(
                    f"INTEGRITY_CONFLICT: {collection_name} evidence changed"
                )
        return new, reused

    async def build(
        self,
        *,
        symbol: str,
        decision_time: datetime,
        source_trade_date: date,
        source_snapshot_id: str,
        execute: bool,
        provider: DecisionEvidenceProvider | None = None,
        fetched: DecisionEvidenceFetchResult | None = None,
        timeout_seconds: float = 180,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        market, symbol = normalize_instrument(symbol, "CN")
        if market != "CN" or source_trade_date != decision_time.date():
            raise ValueError("Decision Evidence Pack identity is invalid")
        provider = provider or AKShareDecisionEvidenceProvider()
        if fetched is None:
            fetched = await asyncio.wait_for(
                asyncio.to_thread(
                    provider.fetch,
                    symbol=symbol,
                    decision_time=decision_time,
                ),
                timeout=timeout_seconds,
            )
        collected_at = collected_at or datetime.utcnow()
        documents = self._documents(fetched, collected_at=collected_at)
        manifest = self._manifest(
            symbol=symbol,
            decision_time=decision_time,
            source_trade_date=source_trade_date,
            source_snapshot_id=source_snapshot_id,
            result=fetched,
            documents=documents,
            created_at=collected_at,
        )
        existing = clean_document(
            await self.db[self.COLLECTION].find_one(
                {"manifest_id": manifest.manifest_id}
            )
        )
        if existing is not None:
            stored = DecisionEvidencePackManifest.model_validate(existing)
            if (
                not self.verify_integrity(stored)
                or stored.manifest_hash != manifest.manifest_hash
            ):
                raise DecisionEvidencePackConflict(
                    "INTEGRITY_CONFLICT: immutable Decision Evidence Pack changed"
                )
            return {
                "status": stored.overall_status,
                "action": "REUSED",
                "write": execute,
                "manifest": stored.model_dump(mode="json"),
                "source_writes": {"created": 0, "reused": len(stored.ordered_evidence_refs)},
            }

        financial_docs = [item[1] for item in documents["financial_evidence"]]
        dividend_docs = [
            item[1]
            for item in documents["dividend_evidence"]
            if item[0].startswith("decision_dividend:")
        ]
        action_docs = [item[1] for item in documents["corporate_actions"]]
        announcement_docs = [item[1] for item in documents["announcement_evidence"]]
        pending: list[tuple[str, list[dict[str, Any]]]] = []
        reused = 0
        for collection_name, source_documents in (
            (self.FINANCIAL_COLLECTION, financial_docs),
            (self.DIVIDEND_COLLECTION, dividend_docs + action_docs),
            (self.ANNOUNCEMENT_COLLECTION, announcement_docs),
        ):
            new, count = await self._check_documents(collection_name, source_documents)
            pending.append((collection_name, new))
            reused += count
        created = 0
        action = "WOULD_CREATE"
        if execute:
            for collection_name, source_documents in pending:
                for document in source_documents:
                    await self.db[collection_name].insert_one(
                        to_mongo_value(document)
                    )
                    created += 1
            await self.db[self.COLLECTION].insert_one(model_document(manifest))
            action = "CREATED"
        return {
            "status": manifest.overall_status,
            "action": action,
            "write": execute,
            "manifest": manifest.model_dump(mode="json"),
            "source_writes": {"created": created, "reused": reused},
        }

    async def get_for_snapshot(
        self,
        *,
        source_snapshot_id: str,
        symbol: str,
        source_trade_date: date,
    ) -> DecisionEvidencePackManifest | None:
        rows = await self.db[self.COLLECTION].find(
            {
                "source_snapshot_id": source_snapshot_id,
                "symbol": symbol,
                "source_trade_date": datetime.combine(
                    source_trade_date, datetime.min.time()
                ),
                "schema_version": DECISION_EVIDENCE_PACK_SCHEMA_VERSION,
                "calculation_version": DECISION_EVIDENCE_CALCULATION_VERSION,
            }
        ).limit(2).to_list(length=2)
        if not rows:
            return None
        if len(rows) != 1:
            raise DecisionEvidencePackConflict(
                "INTEGRITY_CONFLICT: Decision Evidence Pack identity is ambiguous"
            )
        manifest = DecisionEvidencePackManifest.model_validate(clean_document(rows[0]))
        if not self.verify_integrity(manifest):
            raise DecisionEvidencePackConflict(
                "INTEGRITY_CONFLICT: Decision Evidence Pack hash mismatch"
            )
        return manifest
