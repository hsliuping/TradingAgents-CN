"""Best-effort Candidate synchronization for TOP_CONFIRMED orders only."""

from __future__ import annotations

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_storage import clean_document


class PaperCandidateSyncService:
    def __init__(self, db):
        self.db = db
        self.candidates = CandidatePoolService(db=db)
        self.audit = PaperAuditService(db)

    async def sync_order(self, order, *, trace_id: str | None = None) -> None:
        if (
            order.account_type != "PAPER_TOP_CONFIRMED"
            or not order.candidate_id
        ):
            return
        position = clean_document(
            await self.db["ag_paper_positions"].find_one(
                {
                    "account_id": order.account_id,
                    "market": "CN",
                    "symbol": order.symbol,
                }
            )
        )
        quantity = int(position.get("quantity", 0)) if position else 0
        try:
            await self.candidates.sync_top_confirmed_paper_state(
                candidate_id=order.candidate_id,
                user_id=order.user_id,
                account_id=order.account_id,
                order_id=order.order_id,
                order_status=order.status,
                position_quantity=quantity,
                trace_id=trace_id,
            )
        except Exception as exc:
            await self.audit.record(
                "CANDIDATE_SYNC_FAILED",
                (
                    "candidate synchronization failed without rolling back "
                    f"paper assets: {type(exc).__name__}: {str(exc)[:300]}"
                ),
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                symbol=order.symbol,
                source_type=order.source_type,
                source_object_id=order.source_object_id,
                risk_decision_id=order.risk_decision_id,
                trace_id=trace_id,
            )
