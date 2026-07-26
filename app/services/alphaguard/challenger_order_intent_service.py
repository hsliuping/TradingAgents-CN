"""Internal-only PAPER_CHALLENGER intent creation.

There is intentionally no public API for this service and no formal execution
outbox event.  A Challenger output must contain a complete isolated
NormalPlan -> TopReview -> Consensus -> HardRisk chain.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import ExperimentRepository
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.decision_control_schemas import (
    ConsensusDecision,
    RiskDecision,
)
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChallengerAssignment,
    ExperimentOutputPair,
)
from tradingagents.alphaguard.paper_schemas import (
    OrderIntent,
    PAPER_SCHEMA_VERSION,
    paper_canonical_hash,
)


class ChallengerIntentError(ValueError):
    pass


class ChallengerOrderIntentService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.registry = ExperimentRegistry(db)
        self.accounts = PaperAccountService(db)
        self.calendar = PaperTradingCalendarService(db)
        self.policies = PaperPolicyRegistry(db)
        self.snapshots = EvidenceSnapshotService(db=db)
        self.audit = ExperimentAuditService(db)

    async def create_from_output(
        self,
        *,
        output_id: str,
        assignment_id: str,
        now: datetime | None = None,
    ) -> OrderIntent:
        now = now or datetime.utcnow()
        output_raw = await self.repository.get(
            "shadow_outputs", {"output_id": output_id}
        )
        assignment_raw = await self.repository.get(
            "challenger_assignments", {"assignment_id": assignment_id}
        )
        if output_raw is None or assignment_raw is None:
            raise ChallengerIntentError(
                "experiment output and active assignment are required"
            )
        output = ExperimentOutputPair.model_validate(output_raw)
        assignment = ChallengerAssignment.model_validate(assignment_raw)
        if (
            assignment.status != "ACTIVE"
            or output.experiment_id != assignment.experiment_id
            or output.run_type != "PAPER_CHALLENGER"
        ):
            raise ChallengerIntentError(
                "output is not eligible for active PAPER_CHALLENGER execution"
            )
        definition = await self.registry.get(assignment.experiment_id)
        if definition.status != "CHALLENGER":
            raise ChallengerIntentError("experiment is not CHALLENGER")
        chain = output.challenger_output
        try:
            plan = NormalTradePlan.model_validate(chain["normal_trade_plan"])
            review = TopReviewDecision.model_validate(
                chain["top_review_decision"]
            )
            consensus = ConsensusDecision.model_validate(
                chain["consensus_decision"]
            )
            risk = RiskDecision.model_validate(chain["risk_decision"])
        except (KeyError, ValueError) as exc:
            raise ChallengerIntentError(
                "complete isolated decision chain is required"
            ) from exc
        if (
            plan.status != "PROPOSE_TRADE"
            or review.status not in {"CONFIRM", "RISK_ADJUST"}
            or consensus.status != "CONSENSUS_PASS"
            or risk.status not in {"PASS", "REDUCE"}
            or consensus.final_plan is None
            or risk.consensus_id != consensus.consensus_id
            or consensus.plan_id != plan.plan_id
            or risk.snapshot_id != output.snapshot_id
            or consensus.snapshot_id != output.snapshot_id
        ):
            raise ChallengerIntentError(
                "Challenger decision chain did not pass all gates"
            )
        if (
            risk.approved_quantity is None
            or risk.approved_quantity <= 0
            or risk.earliest_eligible_execute_at is None
            or risk.account_id != assignment.account_id
        ):
            raise ChallengerIntentError(
                "HardRisk quantity, account and execution date are required"
            )
        account = await self.accounts.get_account(
            assignment.account_id, user_id=assignment.user_id
        )
        if (
            account is None
            or account.account_type != "PAPER_CHALLENGER"
            or account.status != "ACTIVE"
        ):
            raise ChallengerIntentError("PAPER_CHALLENGER account is unavailable")
        snapshot = await self.snapshots.get(
            output.snapshot_id, assignment.user_id
        )
        if snapshot is None or not self.snapshots.verify_integrity(snapshot):
            raise ChallengerIntentError("EvidenceSnapshot is missing or tampered")
        final_plan = consensus.final_plan
        if (
            final_plan.symbol != output.symbol
            or final_plan.market != output.market
            or final_plan.snapshot_id != output.snapshot_id
        ):
            raise ChallengerIntentError("final plan identity differs from Shadow")
        if final_plan.valid_until and now > final_plan.valid_until:
            raise ChallengerIntentError("Challenger final plan is expired")
        execution = await self.policies.execution_policy()
        fee = await self.policies.fee_policy()
        earliest, expires = await self.calendar.execution_window(
            earliest_date=risk.earliest_eligible_execute_at.date(),
            validity_sessions=execution.validity_sessions,
        )
        if final_plan.action == "BUY":
            if final_plan.entry_zone is None:
                raise ChallengerIntentError(
                    "BUY Challenger plan requires a reliable entry zone"
                )
            order_type = "LIMIT"
            limit_price = Decimal(str(final_plan.entry_zone.upper))
            side = "BUY"
        else:
            order_type = "MARKET_ON_OPEN"
            limit_price = None
            side = "SELL"
        idempotency_key = paper_canonical_hash(
            {
                "account_id": assignment.account_id,
                "source_type": "CHALLENGER",
                "output_id": output_id,
                "assignment_id": assignment_id,
                "risk_decision_id": risk.risk_decision_id,
                "execution_policy_version": execution.version,
            }
        )
        existing = clean_document(
            await self.db["ag_order_intents"].find_one(
                {"idempotency_key": idempotency_key}
            )
        )
        if existing:
            return OrderIntent.model_validate(existing)
        payload = {
            "intent_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:challenger-intent:{idempotency_key}",
                )
            ),
            "user_id": assignment.user_id,
            "account_id": assignment.account_id,
            "account_type": "PAPER_CHALLENGER",
            "source_type": "CHALLENGER",
            "source_object_id": output_id,
            "analysis_id": plan.analysis_id,
            "candidate_id": None,
            "snapshot_id": output.snapshot_id,
            "quant_proposal_id": risk.quant_proposal_id,
            "plan_id": final_plan.plan_id,
            "consensus_id": consensus.consensus_id,
            "risk_decision_id": risk.risk_decision_id,
            "experiment_id": assignment.experiment_id,
            "assignment_id": assignment.assignment_id,
            "symbol": output.symbol,
            "market": "CN",
            "currency": "CNY",
            "original_action": final_plan.action,
            "side": side,
            "order_type": order_type,
            "quantity": risk.approved_quantity,
            "limit_price": limit_price,
            "earliest_execute_at": earliest,
            "expires_at": expires,
            "execution_policy_version": execution.version,
            "matching_engine_version": execution.matching_engine_version,
            "fee_policy_version": fee.version,
            "account_state_snapshot_id": (
                await self.accounts.account_state_hash(assignment.account_id)
            ),
            "idempotency_key": idempotency_key,
            "created_at": now,
            "schema_version": PAPER_SCHEMA_VERSION,
            "benchmark_only": False,
            "consensus_approved": True,
            "hard_risk_approved": True,
            "execution_environment": "PAPER",
            "live_execution_allowed": False,
        }
        payload["immutable_hash"] = paper_canonical_hash(
            payload,
            exclude={"intent_id", "immutable_hash", "created_at"},
        )
        intent = OrderIntent.model_validate(payload)
        await self.db["ag_order_intents"].insert_one(model_document(intent))
        await self.audit.record(
            "CHALLENGER_ASSIGNED",
            "internal PAPER_CHALLENGER intent created from full isolated chain",
            experiment_id=assignment.experiment_id,
            assignment_id=assignment.assignment_id,
            run_id=output.run_id,
            user_id=assignment.user_id,
            market=assignment.market,
            input_hash=intent.immutable_hash,
        )
        return intent
