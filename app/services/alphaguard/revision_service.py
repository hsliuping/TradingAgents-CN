"""Create the single allowed material-revision request."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import RevisionRequest
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)


REVISION_CONSTRAINTS = [
    "revision_round must equal 1",
    "snapshot_id, quant_proposal_id, symbol, market and strategy are immutable",
    "trade action cannot reverse QuantTradeProposal direction",
    "all evidence must exist in DecisionContext",
    "no data outside EvidenceSnapshot may be introduced",
    "there is no second return to the normal model",
]


class RevisionService:
    def __init__(self, db):
        self.db = db

    async def create(
        self,
        *,
        analysis_id: str,
        plan: NormalTradePlan,
        review: TopReviewDecision,
    ) -> RevisionRequest:
        if plan.revision_round != 0 or review.status != "MATERIAL_REVISION":
            raise ValueError("revision request requires round-0 MATERIAL_REVISION")
        identity = (
            f"{analysis_id}:{plan.plan_id}:{review.review_id}:revision-round-1"
        )
        request = RevisionRequest(
            revision_request_id=str(uuid5(NAMESPACE_URL, identity)),
            analysis_id=analysis_id,
            snapshot_id=plan.snapshot_id,
            original_plan_id=plan.plan_id,
            review_id=review.review_id,
            requested_changes=review.material_change_fields,
            material_change_fields=review.material_change_fields,
            risk_findings=review.risk_findings,
            constraints=REVISION_CONSTRAINTS,
            created_at=datetime.utcnow(),
        )
        existing = await self.db["ag_revision_requests"].find_one(
            {"revision_request_id": request.revision_request_id}
        )
        if existing:
            existing.pop("_id", None)
            return RevisionRequest.model_validate(existing)
        await self.db["ag_revision_requests"].insert_one(
            request.model_dump(mode="python")
        )
        return request
