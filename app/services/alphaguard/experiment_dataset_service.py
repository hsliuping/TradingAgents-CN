"""Create-only, fixed EvidenceSnapshot dataset manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_repository import ExperimentRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.evidence_schemas import EvidenceSnapshot
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentDatasetManifest,
    experiment_hash,
)


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class ExperimentDatasetService:
    def __init__(self, db):
        self.db = db
        self.snapshots = EvidenceSnapshotService(db=db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)

    async def create_manifest(
        self,
        *,
        experiment_id: str,
        market: str,
        snapshot_ids: list[str],
        created_from_cutoff_at: datetime,
        selection_rule: str,
        candidate_source_filters: list[str] | None = None,
        data_quality_filters: list[str] | None = None,
        now: datetime | None = None,
    ) -> ExperimentDatasetManifest:
        now = now or datetime.utcnow()
        ids = sorted(set(str(item) for item in snapshot_ids if str(item)))
        if not ids:
            raise ValueError("dataset manifest requires fixed snapshot_ids")
        documents = await self.db["ag_evidence_snapshots"].find(
            {"snapshot_id": {"$in": ids}}
        ).to_list(length=None)
        try:
            by_id = {
                str(item["snapshot_id"]): EvidenceSnapshot.model_validate(
                    clean_document(item)
                )
                for item in documents
            }
        except ValidationError as exc:
            raise ValueError("manifest contains a tampered snapshot") from exc
        missing = sorted(set(ids) - set(by_id))
        if missing:
            raise LookupError(f"manifest snapshots do not exist: {missing}")
        snapshots = [by_id[item] for item in ids]
        for snapshot in snapshots:
            if not self.snapshots.verify_integrity(snapshot):
                raise ValueError(
                    f"snapshot immutable hash mismatch: {snapshot.snapshot_id}"
                )
            if snapshot.market != market:
                raise ValueError("manifest cannot mix markets")
            if _utc(snapshot.created_at) > _utc(created_from_cutoff_at):
                raise ValueError("future-created snapshot cannot enter manifest")
            if _utc(snapshot.price_cutoff_at) > _utc(created_from_cutoff_at):
                raise ValueError("future-cutoff snapshot cannot enter manifest")
        start = min(item.trade_date for item in snapshots)
        end = max(item.trade_date for item in snapshots)
        source_hashes = {
            "ag_evidence_snapshots": experiment_hash(
                [
                    {
                        "snapshot_id": item.snapshot_id,
                        "immutable_hash": item.immutable_hash,
                    }
                    for item in snapshots
                ]
            ),
            "raw_refs": experiment_hash(
                {
                    item.snapshot_id: item.raw_refs
                    for item in snapshots
                }
            ),
        }
        content = {
            "experiment_id": experiment_id,
            "market": market,
            "symbols": sorted({item.symbol for item in snapshots}),
            "snapshot_ids": ids,
            "start_trade_date": start,
            "end_trade_date": end,
            "selection_rule": selection_rule,
            "candidate_source_filters": sorted(
                set(candidate_source_filters or [])
            ),
            "data_quality_filters": sorted(set(data_quality_filters or [])),
            "price_data_versions": sorted(
                {item.price_data_version for item in snapshots}
            ),
            "financial_data_versions": sorted(
                {item.financial_data_version for item in snapshots}
            ),
            "factor_input_versions": sorted(
                {
                    f"{factor_id}@{version}"
                    for item in snapshots
                    for factor_id, version in item.factor_version_set.items()
                }
            ),
            "created_from_cutoff_at": created_from_cutoff_at,
            "source_collection_hashes": source_hashes,
        }
        manifest_hash = experiment_hash(content)
        manifest = ExperimentDatasetManifest(
            dataset_manifest_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:experiment-manifest:{manifest_hash}",
                )
            ),
            manifest_hash=manifest_hash,
            created_at=now,
            **content,
        )
        stored, created = await self.repository.save_immutable(
            "dataset_manifests",
            manifest,
            identity={"manifest_hash": manifest_hash},
            hash_field="manifest_hash",
        )
        if created:
            await self.audit.record(
                "DATASET_MANIFEST_CREATED",
                f"fixed manifest created with {len(ids)} snapshots",
                experiment_id=experiment_id,
                dataset_manifest_id=stored.dataset_manifest_id,
                market=market,
                input_hash=manifest_hash,
            )
        return stored

    async def get(
        self, dataset_manifest_id: str
    ) -> ExperimentDatasetManifest:
        raw = await self.repository.get(
            "dataset_manifests",
            {"dataset_manifest_id": dataset_manifest_id},
        )
        if raw is None:
            raise LookupError("ExperimentDatasetManifest does not exist")
        manifest = ExperimentDatasetManifest.model_validate(raw)
        await self.verify(manifest)
        return manifest

    async def verify(self, manifest: ExperimentDatasetManifest) -> None:
        calculated_manifest_hash = experiment_hash(
            manifest,
            exclude={
                "dataset_manifest_id",
                "manifest_hash",
                "created_at",
                "schema_version",
            },
        )
        if calculated_manifest_hash != manifest.manifest_hash:
            raise ValueError("manifest immutable content hash mismatch")
        documents = await self.db["ag_evidence_snapshots"].find(
            {"snapshot_id": {"$in": manifest.snapshot_ids}}
        ).to_list(length=None)
        if len(documents) != len(manifest.snapshot_ids):
            raise ValueError("manifest snapshot set is incomplete")
        snapshots = [
            EvidenceSnapshot.model_validate(clean_document(item))
            for item in documents
        ]
        for snapshot in snapshots:
            if not self.snapshots.verify_integrity(snapshot):
                raise ValueError("manifest contains a tampered snapshot")
            if _utc(snapshot.created_at) > _utc(manifest.created_from_cutoff_at):
                raise ValueError("manifest contains a future-created snapshot")
            if _utc(snapshot.price_cutoff_at) > _utc(
                manifest.created_from_cutoff_at
            ):
                raise ValueError("manifest contains a future-cutoff snapshot")
        source_hash = experiment_hash(
            sorted(
                (
                    {
                        "snapshot_id": item.snapshot_id,
                        "immutable_hash": item.immutable_hash,
                    }
                    for item in snapshots
                ),
                key=lambda item: item["snapshot_id"],
            )
        )
        if (
            source_hash
            != manifest.source_collection_hashes["ag_evidence_snapshots"]
        ):
            raise ValueError("manifest source collection hash mismatch")
        raw_ref_hash = experiment_hash(
            {
                item.snapshot_id: item.raw_refs
                for item in sorted(snapshots, key=lambda value: value.snapshot_id)
            }
        )
        if raw_ref_hash != manifest.source_collection_hashes["raw_refs"]:
            raise ValueError("manifest raw reference hash mismatch")
