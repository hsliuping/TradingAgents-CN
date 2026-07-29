"""Idempotent persisted-data production observation for five selected symbols."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.decision_pipeline import DecisionPipeline
from app.services.alphaguard.evaluation_subject_builder import (
    EvaluationSubjectBuilder,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.market_context_window_service import (
    MarketContextWindowService,
)
from app.services.alphaguard.paper_storage import clean_document, mongo_date
from app.services.alphaguard.production_data_config import (
    cn_price_limit_policy,
    production_market_context_policy,
)
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.real_data_candidate_service import (
    CandidateRealDataService,
)
from app.services.alphaguard.strategy_registry import STRATEGY_SET_VERSION
from tradingagents.alphaguard.backfill_schemas import backfill_hash
from tradingagents.alphaguard.evidence_schemas import EvidenceSnapshot
from tradingagents.alphaguard.instruments import normalize_instrument


class ProductionObservationError(RuntimeError):
    pass


FORMAL_TRADING_COLLECTIONS = (
    "ag_execution_outbox",
    "ag_order_intents",
    "ag_paper_orders",
    "ag_paper_fills",
    "ag_paper_accounts",
    "ag_paper_positions",
    "ag_paper_position_lots",
    "ag_paper_reservations",
    "ag_paper_ledger_entries",
    "ag_settlement_records",
    "ag_paper_account_snapshots",
)


class ProductionObservationService:
    def __init__(self, db):
        self.db = db
        self.data = CandidateRealDataService(db)
        self.candidates = CandidatePoolService(db)
        self.snapshots = EvidenceSnapshotService(db=db)
        self.quant = QuantResearchPipeline(db)

    async def _state(self) -> dict[str, dict[str, Any]]:
        state = {}
        for name in FORMAL_TRADING_COLLECTIONS:
            documents = [
                clean_document(item)
                for item in await self.db[name].find({}).to_list(length=None)
            ]
            state[name] = {
                "count": len(documents),
                "content_hash": backfill_hash(
                    sorted(documents, key=backfill_hash)
                ),
            }
        return state

    async def _candidate(self, user_id: str, symbol: str):
        candidate = await self.candidates.get_by_identity(
            str(user_id),
            "CN",
            symbol,
        )
        if candidate is None:
            raise ProductionObservationError(
                f"{symbol} is not an existing user-selected candidate"
            )
        if "USER_SELECTED" not in {
            str(item.value if hasattr(item, "value") else item)
            for item in candidate.sources
        }:
            raise ProductionObservationError(
                f"{symbol} candidate lacks USER_SELECTED lineage"
            )
        return candidate

    async def _existing_snapshot(
        self,
        *,
        user_id: str,
        symbol: str,
        trade_date: date,
        market_context_id: str,
        raw_refs: dict[str, list[str]],
    ) -> EvidenceSnapshot | None:
        rows = await self.db["ag_evidence_snapshots"].find(
            {
                "user_id": str(user_id),
                "symbol": symbol,
                "market": "CN",
                "trade_date": mongo_date(trade_date),
                "market_context_id": market_context_id,
            }
        ).to_list(length=2)
        if len(rows) > 1:
            raise ProductionObservationError(
                f"{symbol} has duplicate production snapshots for one trade date"
            )
        if not rows:
            return None
        snapshot = EvidenceSnapshot.model_validate(clean_document(rows[0]))
        if not self.snapshots.verify_integrity(snapshot):
            raise ProductionObservationError(
                f"{symbol} existing snapshot failed immutable hash verification"
            )
        expected_refs = {
            key: sorted(value) for key, value in sorted(raw_refs.items())
        }
        stored_refs = {
            key: sorted(value)
            for key, value in sorted(snapshot.raw_refs.items())
        }
        if stored_refs != expected_refs:
            raise ProductionObservationError(
                f"{symbol} existing snapshot references conflict with persisted inputs"
            )
        return snapshot

    async def run(
        self,
        *,
        user_id: str,
        symbols: list[str],
        trade_date: date,
        cutoff_at: datetime,
        execute: bool,
        trace_id: str,
    ) -> dict[str, Any]:
        normalized = sorted(
            {normalize_instrument(symbol, "CN")[1] for symbol in symbols}
        )
        if not 3 <= len(normalized) <= 5:
            raise ProductionObservationError(
                "production observation requires the 3 to 5 selected candidates"
            )
        if cutoff_at.date() != trade_date or cutoff_at.hour < 15:
            raise ProductionObservationError(
                "production observation requires an after-close same-day cutoff"
            )
        context_policy = production_market_context_policy()
        context_rows = await self.db["ag_market_contexts"].find(
            {
                "market": "CN",
                "trade_date": mongo_date(trade_date),
                "calculation_status": "READY",
                "calculation_version": context_policy[
                    "calculation_version"
                ],
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).limit(2).to_list(length=2)
        if len(context_rows) > 1:
            raise ProductionObservationError(
                "exact-date production MarketContext identity is ambiguous"
            )
        context = clean_document(context_rows[0]) if context_rows else None
        if context is None:
            raise ProductionObservationError(
                "exact-date READY production MarketContext is missing"
            )
        context_window = await MarketContextWindowService(self.db).get_ready(
            as_of_trade_date=trade_date,
            cutoff_at=cutoff_at,
        )
        trading_policy = cn_price_limit_policy()
        trading_statuses = await self.db["ag_security_trading_statuses"].find(
            {
                "symbol": {"$in": normalized},
                "market": "CN",
                "trade_date": mongo_date(trade_date),
                "calculation_status": "READY",
                "calculation_version": trading_policy[
                    "calculation_version"
                ],
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).to_list(length=None)
        status_counts = {
            symbol: sum(
                str(item.get("symbol")) == symbol
                for item in trading_statuses
            )
            for symbol in normalized
        }
        invalid_status = {
            symbol: count
            for symbol, count in status_counts.items()
            if count != 1
        }
        if invalid_status:
            raise ProductionObservationError(
                "versioned trading status is not uniquely READY for "
                f"{invalid_status}"
            )
        factor_versions = await FactorRegistry(self.db).get_version_set(
            require_registered=True
        )
        before_state = await self._state()
        results = []
        triggered_proposals = []
        for symbol in normalized:
            candidate = await self._candidate(user_id, symbol)
            precheck = await self.data.precheck_candidate(
                symbol=symbol,
                trade_date=trade_date,
                cutoff_at=cutoff_at,
            )
            quality_status = str(precheck["data_quality"]["status"])
            if quality_status == "FAIL":
                results.append(
                    {
                        "symbol": symbol,
                        "status": "DATA_QUALITY_FAIL",
                        "data_quality": precheck["data_quality"],
                    }
                )
                continue
            if not precheck["snapshot_preconditions"]["market_context_exists"]:
                raise ProductionObservationError(
                    f"{symbol} precheck did not resolve exact production MarketContext"
                )
            raw_refs = {
                key: list(value)
                for key, value in precheck["raw_refs"].items()
            }
            raw_refs["market_context_window"] = [
                f"market_context_window:{context_window.manifest_id}"
            ]
            snapshot = await self._existing_snapshot(
                user_id=str(user_id),
                symbol=symbol,
                trade_date=trade_date,
                market_context_id=str(context["context_id"]),
                raw_refs=raw_refs,
            )
            snapshot_action = "REUSED" if snapshot else "WOULD_CREATE"
            proposals = []
            if execute:
                if snapshot is None:
                    snapshot = await self.snapshots.create(
                        user_id=str(user_id),
                        payload={
                            "analysis_id": (
                                f"alphaguard-production:{candidate.candidate_id}:"
                                f"{trade_date.isoformat()}"
                            ),
                            "symbol": symbol,
                            "market": "CN",
                            "trade_date": trade_date,
                            "price_cutoff_at": cutoff_at,
                            "news_cutoff_at": cutoff_at,
                            "announcement_cutoff_at": cutoff_at,
                            "price_data_version": precheck["versions"][
                                "price_data_version"
                            ],
                            "financial_data_version": precheck["versions"][
                                "financial_data_version"
                            ],
                            "news_data_version": precheck["versions"][
                                "news_data_version"
                            ],
                            "market_context_id": str(context["context_id"]),
                            "raw_refs": raw_refs,
                            "factor_version_set": factor_versions,
                            "strategy_version": STRATEGY_SET_VERSION,
                            "required_sources": [
                                "prices",
                                "benchmark_prices",
                                "market_context",
                                "market_context_window",
                                "trading_calendar",
                            ],
                        },
                    )
                    snapshot_action = "CREATED"
                proposals = await self.quant.evaluate(
                    snapshot.snapshot_id,
                    user_id=str(user_id),
                    candidate_id=candidate.candidate_id,
                    trace_id=trace_id,
                )
                triggered_proposals.extend(
                    item for item in proposals if item.status == "TRIGGERED"
                )
            results.append(
                {
                    "symbol": symbol,
                    "status": "READY" if quality_status != "FAIL" else "BLOCKED",
                    "data_quality_status": quality_status,
                    "snapshot_action": snapshot_action,
                    "snapshot_id": snapshot.snapshot_id if snapshot else None,
                    "snapshot_integrity": (
                        self.snapshots.verify_integrity(snapshot)
                        if snapshot
                        else None
                    ),
                    "proposal_distribution": {
                        status: sum(item.status == status for item in proposals)
                        for status in (
                            "TRIGGERED",
                            "WATCH",
                            "REJECTED",
                            "INSUFFICIENT_DATA",
                            "INVALID_INPUT",
                        )
                    },
                    "proposal_ids": [item.proposal_id for item in proposals],
                }
            )
        decisions = []
        if execute and triggered_proposals:
            account_rows = await self.db["ag_paper_accounts"].find(
                {
                    "user_id": str(user_id),
                    "account_type": "PAPER_TOP_CONFIRMED",
                    "market": "CN",
                    "status": "ACTIVE",
                    "live_execution_allowed": False,
                }
            ).to_list(length=2)
            if len(account_rows) != 1:
                raise ProductionObservationError(
                    "PAPER_TOP_CONFIRMED account identity is not unique and active"
                )
            account_id = str(account_rows[0]["account_id"])
            pipeline = DecisionPipeline(self.db)
            for proposal in sorted(
                triggered_proposals,
                key=lambda item: item.proposal_id,
            ):
                decision = await pipeline.evaluate_quant_proposal(
                    proposal.proposal_id,
                    user_id=str(user_id),
                    account_id=account_id,
                    trace_id=trace_id,
                )
                decisions.append(
                    {
                        "proposal_id": proposal.proposal_id,
                        "terminal_status": decision.terminal_status,
                        "risk_status": (
                            decision.risk_decision.status
                            if decision.risk_decision
                            else None
                        ),
                    }
                )
        subjects_created = subjects_reused = 0
        horizon_label_distribution: dict[str, int] = {}
        if execute:
            subjects, subjects_created, subjects_reused = (
                await EvaluationSubjectBuilder(self.db).discover(
                    user_id=str(user_id),
                    decision_trade_date_lte=trade_date,
                    trace_id=trace_id,
                )
            )
            current_proposal_ids = {
                str(proposal_id)
                for result in results
                for proposal_id in result.get("proposal_ids", [])
            }
            label_service = HorizonLabelService(self.db)
            for subject in subjects:
                if (
                    subject.decision_trade_date != trade_date
                    or subject.source_object_id not in current_proposal_ids
                ):
                    continue
                for label in await label_service.calculate_all(
                    subject,
                    as_of_trade_date=trade_date,
                    trace_id=trace_id,
                ):
                    horizon_label_distribution[label.status] = (
                        horizon_label_distribution.get(label.status, 0) + 1
                    )
        after_state = await self._state()
        if not triggered_proposals and before_state != after_state:
            raise ProductionObservationError(
                "non-triggered observation unexpectedly changed formal trading state"
            )
        return {
            "write": execute,
            "user_id": str(user_id),
            "market": "CN",
            "trade_date": trade_date,
            "cutoff_at": cutoff_at,
            "market_context_id": str(context["context_id"]),
            "market_context_data_version": str(context["data_version"]),
            "context_window_manifest_id": context_window.manifest_id,
            "context_window_manifest_hash": context_window.manifest_hash,
            "context_window_count": context_window.actual_count,
            "results": results,
            "triggered_count": len(triggered_proposals),
            "decisions": decisions,
            "evaluation_subjects_created": subjects_created,
            "evaluation_subjects_reused": subjects_reused,
            "horizon_label_distribution": horizon_label_distribution,
            "formal_trading_state_before": before_state,
            "formal_trading_state_after": after_state,
            "live_execution_allowed": False,
        }
