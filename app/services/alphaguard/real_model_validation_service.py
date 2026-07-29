"""Explicit, research-only real-model validation with a hard execution block."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import RealModelValidationRun
from app.schemas.alphaguard.quant import QuantTradeProposal
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
)

from .consensus_engine import ConsensusEngine
from .decision_context_builder import DecisionContextBuilder
from .hard_risk_engine import HardRiskEngine
from .model_runtime_context import build_model_runtime_context
from .model_runtime_repository import ModelRuntimeRepository
from .model_runtime_status_service import ModelRuntimeStatusService
from .paper_storage import clean_document, safe_error_message
from .profiled_decision_model_runner import ProfiledDecisionModelRunner
from .risk_policy_registry import RiskPolicyRegistry
from .snapshot_research_runtime import SnapshotResearchRuntime


class RealModelValidationService:
    def __init__(self, db):
        self.db = db
        self.repository = ModelRuntimeRepository(db)

    async def _eligible_proposal(
        self,
        *,
        proposal_id: str | None,
        user_id: str | None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {
            "status": "TRIGGERED",
            "action_candidate": {"$in": ["BUY", "SELL", "REDUCE"]},
            "automated_execution_allowed": False,
        }
        if proposal_id:
            query["proposal_id"] = proposal_id
        if user_id:
            query["user_id"] = str(user_id)
        rows = await self.db["ag_quant_proposals"].find(query).sort(
            "trade_date", -1
        ).to_list(length=100)
        for raw in rows:
            proposal = QuantTradeProposal.model_validate(clean_document(raw))
            snapshot = clean_document(
                await self.db["ag_evidence_snapshots"].find_one(
                    {"snapshot_id": proposal.snapshot_id}
                )
            )
            if not snapshot:
                continue
            if (
                snapshot.get("schema_version")
                == EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2
                and snapshot.get("evidence_contract_status") == "COMPLETE"
                and snapshot.get("automated_execution_allowed") is False
                and int(snapshot.get("actual_benchmark_count") or 0)
                >= int(snapshot.get("required_benchmark_count") or 61)
            ):
                return clean_document(raw)
        return None

    async def run(
        self,
        *,
        requested_by: str,
        idempotency_key: str,
        proposal_id: str | None = None,
        user_id: str | None = None,
    ) -> RealModelValidationRun:
        identity = {
            "requested_by": requested_by,
            "idempotency_key": idempotency_key,
            "proposal_id": proposal_id,
            "user_id": user_id,
            "run_mode": "REAL_MODEL_VALIDATION",
        }
        validation_run_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:real-model-validation:{canonical_hash(identity)}",
            )
        )
        existing = await self.repository.get(
            "validation_runs",
            {"validation_run_id": validation_run_id},
        )
        if existing is not None:
            return RealModelValidationRun.model_validate(existing)

        started = datetime.now(timezone.utc)
        status = "CREATED"
        snapshot_id = None
        selected_id = None
        research_ids: list[str] = []
        normal_run_id = None
        top_run_id = None
        consensus_status = None
        hard_risk_status = None
        try:
            readiness = await ModelRuntimeStatusService(self.db).status(
                admin=True
            )
            if readiness["status"] != "READY":
                status = "MODEL_NOT_CONFIGURED"
            else:
                selected = await self._eligible_proposal(
                    proposal_id=proposal_id,
                    user_id=user_id,
                )
                if selected is None:
                    status = "NO_ELIGIBLE_SAMPLE"
                else:
                    selected_id = str(selected["proposal_id"])
                    snapshot_id = str(selected["snapshot_id"])
                    context, resolved = await DecisionContextBuilder(
                        self.db
                    ).build(
                        selected_id,
                        user_id=str(selected["user_id"]),
                        allow_reprocess_model_validation=True,
                        persist=False,
                    )
                    model_context = build_model_runtime_context(
                        context, resolved
                    )
                    research_runtime = SnapshotResearchRuntime(self.db)
                    research = await research_runtime.run(
                        analysis_id=context.analysis_id,
                        context=model_context,
                        run_mode="REAL_MODEL_VALIDATION",
                    )
                    research.append(
                        await research_runtime.disabled_social_result(
                            analysis_id=context.analysis_id,
                            context=model_context,
                        )
                    )
                    research_ids = [
                        item.research_result_id for item in research
                    ]
                    if any(
                        item.status
                        not in {
                            "SUCCESS",
                            "INSUFFICIENT_DATA",
                            "DISABLED_NOT_REQUIRED",
                        }
                        for item in research
                    ):
                        status = "FAILED"
                    else:
                        runner = await ProfiledDecisionModelRunner.create(
                            db=self.db,
                            run_mode="REAL_MODEL_VALIDATION",
                            automated_execution_allowed=False,
                            model_runtime_context_hash=(
                                model_context.context_hash
                            ),
                            research_results=[
                                item.model_dump(mode="json")
                                for item in research
                            ],
                        )
                        normal = await runner.run_normal(
                            context=context,
                            attempt_number=1,
                            trace_id=validation_run_id,
                        )
                        normal_doc = await self.db["ag_model_runs"].find_one(
                            {
                                "analysis_id": context.analysis_id,
                                "model_profile_id": (
                                    runner.normal_profile.profile_id
                                ),
                                "request_hash": normal.model_meta.input_hash,
                            }
                        )
                        normal_run_id = (
                            str(normal_doc["model_run_id"])
                            if normal_doc
                            else None
                        )
                        if normal.status != "PROPOSE_TRADE":
                            status = "COMPLETED"
                        else:
                            policy = await RiskPolicyRegistry(
                                self.db
                            ).get_active()
                            review = await runner.run_top(
                                context=context,
                                plan=normal,
                                risk_policy_summary=policy.model_dump(
                                    mode="json",
                                    exclude={"created_at", "config_hash"},
                                ),
                                attempt_number=1,
                                trace_id=validation_run_id,
                            )
                            top_doc = await self.db[
                                "ag_model_runs"
                            ].find_one(
                                {
                                    "analysis_id": context.analysis_id,
                                    "model_profile_id": (
                                        runner.top_profile.profile_id
                                    ),
                                    "request_hash": (
                                        review.model_meta.input_hash
                                    ),
                                }
                            )
                            top_run_id = (
                                str(top_doc["model_run_id"])
                                if top_doc
                                else None
                            )
                            consensus = ConsensusEngine().evaluate(
                                context=context,
                                plan=normal,
                                review=review,
                                now=datetime.now(timezone.utc),
                            )
                            consensus_status = consensus.status
                            if consensus.status == "CONSENSUS_PASS":
                                hard_risk = HardRiskEngine().evaluate(
                                    data=resolved,
                                    context=context,
                                    consensus=consensus,
                                    policy=policy,
                                    account_id=None,
                                    now=datetime.now(timezone.utc),
                                )
                                hard_risk_status = hard_risk.status
                            status = "COMPLETED"
        except Exception as exc:
            status = "FAILED"
            # Only the exception class is incorporated into the immutable
            # result. The sanitized text remains server-side operational data.
            safe_error_message(exc)

        result_payload = {
            "validation_run_id": validation_run_id,
            "requested_by": requested_by,
            "snapshot_id": snapshot_id,
            "quant_proposal_id": selected_id,
            "status": status,
            "research_result_ids": research_ids,
            "normal_model_run_id": normal_run_id,
            "top_model_run_id": top_run_id,
            "consensus_status": consensus_status,
            "hard_risk_status": hard_risk_status,
            "execution_gate_status": "BLOCKED_VALIDATION_MODE",
            "input_hash": canonical_hash(identity),
            "created_at": started,
            "completed_at": datetime.now(timezone.utc),
        }
        result_payload["result_hash"] = canonical_hash(
            result_payload,
            exclude={"result_hash", "created_at", "completed_at"},
        )
        result = RealModelValidationRun.model_validate(result_payload)
        saved, _ = await self.repository.save_immutable(
            "validation_runs",
            result,
            identity={"validation_run_id": validation_run_id},
            hash_field="result_hash",
        )
        return saved
