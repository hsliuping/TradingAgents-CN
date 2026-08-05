"""Discover the complete PR-004--PR-006 lineage as immutable subjects."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_audit_service import EvaluationAuditService
from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.decision_schemas import EvidenceRef, PriceRange
from tradingagents.alphaguard.evaluation_schemas import (
    EvaluationSubject,
    evaluation_hash,
)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    parsed = _as_datetime(value)
    if parsed is not None:
        return parsed.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _evidence(items: Iterable[Any]) -> list[EvidenceRef]:
    result: dict[str, EvidenceRef] = {}
    for item in items:
        try:
            ref = item if isinstance(item, EvidenceRef) else EvidenceRef.model_validate(item)
        except Exception:
            continue
        result[ref.evidence_id] = ref
    return [result[key] for key in sorted(result)]


def _status_action(status: str, raw_action: Any) -> str:
    action = str(raw_action or "").upper()
    if action in {"BUY", "SELL", "REDUCE", "HOLD", "WAIT"}:
        return action
    if status in {"WATCH", "WAIT"}:
        return "WAIT"
    if status in {"SUSPEND", "INSUFFICIENT_DATA", "MODEL_FAILED"}:
        return "SUSPEND"
    if status in {
        "REJECT",
        "REJECTED",
        "INVALID_INPUT",
        "INVALID_OUTPUT",
        "CONSENSUS_REJECT",
        "CONSENSUS_INVALID",
    }:
        return "REJECT"
    return "HOLD"


class EvaluationSubjectBuilder:
    def __init__(self, db):
        self.db = db
        self.repository = EvaluationRepository(db)
        self.audit = EvaluationAuditService(db)
        self.version = evaluation_policy().evaluation_version

    async def discover(
        self,
        *,
        user_id: str | None = None,
        decision_trade_date_lte: date | None = None,
        source_object_id: str | None = None,
        evaluation_job_id: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[list[EvaluationSubject], int, int]:
        snapshot_docs = [
            clean_document(item)
            for item in await self.db["ag_evidence_snapshots"].find(
                {"user_id": str(user_id)} if user_id is not None else {}
            ).to_list(length=None)
        ]
        snapshots = {str(item["snapshot_id"]): item for item in snapshot_docs}
        contexts = [
            clean_document(item)
            for item in await self.db["ag_decision_contexts"].find(
                {"user_id": str(user_id)} if user_id is not None else {}
            ).to_list(length=None)
        ]
        context_by_analysis = {
            str(item["analysis_id"]): item for item in contexts
        }
        context_by_snapshot = {
            str(item["snapshot_id"]): item for item in contexts
        }
        account_query = {"user_id": str(user_id)} if user_id is not None else {}
        accounts = [
            clean_document(item)
            for item in await self.db["ag_paper_accounts"].find(account_query).to_list(
                length=None
            )
        ]
        account_map = {str(item["account_id"]): item for item in accounts}
        account_ids = set(account_map)

        intents = [
            clean_document(item)
            for item in await self.db["ag_order_intents"].find(
                {"user_id": str(user_id)} if user_id is not None else {}
            ).to_list(length=None)
        ]
        intent_map = {str(item["intent_id"]): item for item in intents}
        orders = [
            clean_document(item)
            for item in await self.db["ag_paper_orders"].find(
                {"user_id": str(user_id)} if user_id is not None else {}
            ).to_list(length=None)
        ]
        order_map = {str(item["order_id"]): item for item in orders}
        fills = [
            clean_document(item)
            for item in await self.db["ag_paper_fills"].find(
                {"account_id": {"$in": sorted(account_ids)}}
                if user_id is not None
                else {}
            ).to_list(length=None)
        ]
        filled_intents = {
            str(order_map[str(fill["order_id"])]["intent_id"])
            for fill in fills
            if str(fill.get("order_id")) in order_map
        }
        executed_source_ids = {
            str(intent_map[intent_id]["source_object_id"])
            for intent_id in filled_intents
            if intent_id in intent_map
        }

        drafts: list[dict[str, Any]] = []
        quant_query = {"user_id": str(user_id)} if user_id is not None else {}
        for proposal in await self.db["ag_quant_proposals"].find(quant_query).to_list(
            length=None
        ):
            proposal = clean_document(proposal)
            snapshot_id = str(proposal.get("snapshot_id") or "")
            drafts.append(
                self._draft(
                    subject_type="QUANT_PROPOSAL",
                    source=proposal,
                    source_object_id=str(proposal["proposal_id"]),
                    source_object_version=proposal.get("strategy_version"),
                    stage="QUANT",
                    status=str(proposal["status"]),
                    action=_status_action(
                        str(proposal["status"]), proposal.get("action_candidate")
                    ),
                    snapshot_id=snapshot_id,
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(proposal["user_id"]),
                    symbol=str(proposal["symbol"]),
                    market=str(proposal["market"]),
                    decision_trade_date=_as_date(proposal.get("trade_date")),
                    candidate_id=proposal.get("candidate_id"),
                    analysis_id=(
                        context_by_snapshot.get(snapshot_id, {}).get("analysis_id")
                    ),
                    entry_zone=proposal.get("entry_zone"),
                    initial_position_pct=proposal.get("initial_position_pct"),
                    max_position_pct=proposal.get("max_position_pct"),
                    evidence_refs=proposal.get("evidence_refs", []),
                    lineage_ids={
                        "proposal_id": str(proposal["proposal_id"]),
                        "strategy_id": str(proposal.get("strategy_id") or ""),
                        "strategy_version": str(
                            proposal.get("strategy_version") or ""
                        ),
                    },
                    selected_for_execution=(
                        proposal.get("status") == "TRIGGERED"
                    ),
                    actual_execution_exists=str(proposal["proposal_id"])
                    in executed_source_ids,
                )
            )

        report_query = {"user_id": str(user_id)} if user_id is not None else {}
        reports = [
            clean_document(item)
            for item in await self.db["analysis_reports"].find(report_query).to_list(
                length=None
            )
        ]
        plan_by_id: dict[str, dict[str, Any]] = {}
        review_by_id: dict[str, dict[str, Any]] = {}
        for report in reports:
            plans = list(report.get("normal_trade_plan_history") or [])
            if report.get("normal_trade_plan"):
                plans.append(report["normal_trade_plan"])
            for plan in {
                str(item.get("plan_id")): item for item in plans if item
            }.values():
                plan_id = str(plan["plan_id"])
                plan_by_id[plan_id] = plan
                snapshot_id = str(plan.get("snapshot_id") or report.get("snapshot_id") or "")
                context = context_by_analysis.get(str(report.get("analysis_id")), {})
                drafts.append(
                    self._draft(
                        subject_type="NORMAL_PLAN",
                        source=plan,
                        source_object_id=plan_id,
                        source_object_version=(
                            (plan.get("model_meta") or {}).get("model_version")
                        ),
                        stage="NORMAL_MODEL",
                        status=str(plan["status"]),
                        action=_status_action(str(plan["status"]), plan.get("action")),
                        snapshot_id=snapshot_id,
                        snapshots=snapshots,
                        contexts=context_by_snapshot,
                        user_id=str(report.get("user_id") or context.get("user_id")),
                        symbol=str(plan.get("symbol") or context.get("symbol") or report.get("stock_symbol")),
                        market=str(plan.get("market") or context.get("market") or "CN"),
                        decision_trade_date=_as_date(
                            plan.get("trade_date")
                            or context.get("trade_date")
                            or report.get("analysis_date")
                        ),
                        candidate_id=context.get("candidate_id"),
                        analysis_id=str(
                            plan.get("analysis_id")
                            or report.get("analysis_id")
                            or ""
                        )
                        or None,
                        entry_zone=plan.get("entry_zone"),
                        initial_position_pct=plan.get("initial_position_pct"),
                        max_position_pct=plan.get("max_position_pct"),
                        evidence_refs=(
                            list(plan.get("bullish_evidence") or [])
                            + list(plan.get("bearish_evidence") or [])
                        ),
                        lineage_ids={
                            "plan_id": plan_id,
                            "proposal_id": str(plan.get("quant_proposal_id") or ""),
                            "revision_round": str(plan.get("revision_round", 0)),
                            "strategy_id": str(plan.get("strategy_id") or ""),
                            "strategy_version": str(plan.get("strategy_version") or ""),
                        },
                        selected_for_execution=plan.get("status") == "PROPOSE_TRADE",
                        actual_execution_exists=plan_id in executed_source_ids,
                    )
                )

            reviews = list(report.get("top_review_history") or [])
            if report.get("top_review_decision"):
                reviews.append(report["top_review_decision"])
            for review in {
                str(item.get("review_id")): item for item in reviews if item
            }.values():
                review_id = str(review["review_id"])
                review_by_id[review_id] = review
                plan = plan_by_id.get(str(review.get("plan_id")), {})
                adjusted = review.get("adjusted_plan") or {}
                snapshot_id = str(
                    review.get("snapshot_id")
                    or plan.get("snapshot_id")
                    or report.get("snapshot_id")
                    or ""
                )
                context = context_by_analysis.get(str(report.get("analysis_id")), {})
                action = (
                    adjusted.get("action")
                    or plan.get("action")
                    if review.get("status") in {"CONFIRM", "RISK_ADJUST", "MATERIAL_REVISION"}
                    else None
                )
                drafts.append(
                    self._draft(
                        subject_type="TOP_REVIEW",
                        source=review,
                        source_object_id=review_id,
                        source_object_version=(
                            (review.get("model_meta") or {}).get("model_version")
                        ),
                        stage="TOP_MODEL",
                        status=str(review["status"]),
                        action=_status_action(str(review["status"]), action),
                        snapshot_id=snapshot_id,
                        snapshots=snapshots,
                        contexts=context_by_snapshot,
                        user_id=str(report.get("user_id") or context.get("user_id")),
                        symbol=str(
                            adjusted.get("symbol")
                            or plan.get("symbol")
                            or context.get("symbol")
                            or report.get("stock_symbol")
                        ),
                        market=str(
                            adjusted.get("market")
                            or plan.get("market")
                            or context.get("market")
                            or "CN"
                        ),
                        decision_trade_date=_as_date(
                            adjusted.get("trade_date")
                            or plan.get("trade_date")
                            or context.get("trade_date")
                            or report.get("analysis_date")
                        ),
                        candidate_id=context.get("candidate_id"),
                        analysis_id=str(report.get("analysis_id") or "") or None,
                        entry_zone=(
                            adjusted.get("entry_zone")
                            or plan.get("entry_zone")
                        ),
                        initial_position_pct=(
                            adjusted.get("initial_position_pct")
                            if adjusted
                            else plan.get("initial_position_pct")
                        ),
                        max_position_pct=(
                            adjusted.get("max_position_pct")
                            if adjusted
                            else plan.get("max_position_pct")
                        ),
                        evidence_refs=(
                            list(
                                adjusted.get("bullish_evidence")
                                or plan.get("bullish_evidence")
                                or []
                            )
                            + list(
                                adjusted.get("bearish_evidence")
                                or plan.get("bearish_evidence")
                                or []
                            )
                        ),
                        lineage_ids={
                            "review_id": review_id,
                            "plan_id": str(review.get("plan_id") or ""),
                            "proposal_id": str(plan.get("quant_proposal_id") or ""),
                        },
                        selected_for_execution=review.get("status")
                        in {"CONFIRM", "RISK_ADJUST"},
                        actual_execution_exists=False,
                    )
                )

        analysis_ids = set(context_by_analysis)
        for consensus in await self.db["ag_consensus_decisions"].find({}).to_list(
            length=None
        ):
            consensus = clean_document(consensus)
            if str(consensus.get("analysis_id")) not in analysis_ids:
                continue
            context = context_by_analysis[str(consensus["analysis_id"])]
            final_plan = consensus.get("final_plan") or {}
            drafts.append(
                self._draft(
                    subject_type="CONSENSUS",
                    source=consensus,
                    source_object_id=str(consensus["consensus_id"]),
                    source_object_version=consensus.get("consensus_policy_version"),
                    stage="CONSENSUS",
                    status=str(consensus["status"]),
                    action=_status_action(
                        str(consensus["status"]), final_plan.get("action")
                    ),
                    snapshot_id=str(consensus["snapshot_id"]),
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(context["user_id"]),
                    symbol=str(context["symbol"]),
                    market=str(context["market"]),
                    decision_trade_date=_as_date(context.get("trade_date")),
                    candidate_id=context.get("candidate_id"),
                    analysis_id=str(consensus["analysis_id"]),
                    entry_zone=final_plan.get("entry_zone"),
                    initial_position_pct=final_plan.get("initial_position_pct"),
                    max_position_pct=final_plan.get("max_position_pct"),
                    evidence_refs=(
                        list(final_plan.get("bullish_evidence") or [])
                        + list(final_plan.get("bearish_evidence") or [])
                    ),
                    lineage_ids={
                        "consensus_id": str(consensus["consensus_id"]),
                        "plan_id": str(consensus.get("plan_id") or ""),
                        "review_id": str(consensus.get("review_id") or ""),
                        "proposal_id": str(consensus.get("quant_proposal_id") or ""),
                    },
                    selected_for_execution=consensus.get("status") == "CONSENSUS_PASS",
                    actual_execution_exists=False,
                )
            )

        for risk in await self.db["ag_risk_decisions"].find({}).to_list(length=None):
            risk = clean_document(risk)
            if str(risk.get("analysis_id")) not in analysis_ids:
                continue
            context = context_by_analysis[str(risk["analysis_id"])]
            drafts.append(
                self._draft(
                    subject_type="RISK_DECISION",
                    source=risk,
                    source_object_id=str(risk["risk_decision_id"]),
                    source_object_version=risk.get("risk_policy_version"),
                    stage="HARD_RISK",
                    status=str(risk["status"]),
                    action=_status_action(str(risk["status"]), risk.get("action")),
                    snapshot_id=str(risk["snapshot_id"]),
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(context["user_id"]),
                    symbol=str(context["symbol"]),
                    market=str(context["market"]),
                    decision_trade_date=_as_date(context.get("trade_date")),
                    candidate_id=context.get("candidate_id"),
                    analysis_id=str(risk["analysis_id"]),
                    initial_position_pct=risk.get("approved_position_pct"),
                    max_position_pct=risk.get("approved_position_pct"),
                    evidence_refs=[],
                    lineage_ids={
                        "risk_decision_id": str(risk["risk_decision_id"]),
                        "consensus_id": str(risk.get("consensus_id") or ""),
                        "proposal_id": str(risk.get("quant_proposal_id") or ""),
                        "account_id": str(risk.get("account_id") or ""),
                    },
                    selected_for_execution=risk.get("status") in {"PASS", "REDUCE"},
                    actual_execution_exists=str(risk["risk_decision_id"])
                    in executed_source_ids,
                )
            )

        challenger_type_map = {
            "QUANT_PROPOSAL": ("QUANT_PROPOSAL", "QUANT"),
            "NORMAL_PLAN": ("NORMAL_PLAN", "NORMAL_MODEL"),
            "TOP_REVIEW": ("TOP_REVIEW", "TOP_MODEL"),
            "CONSENSUS_DECISION": ("CONSENSUS", "CONSENSUS"),
            "HARD_RISK_DECISION": ("RISK_DECISION", "HARD_RISK"),
        }
        challenger_executed = {
            str(item.get("experiment_id"))
            for item in fills
            if item.get("experiment_id")
        }
        challenger_query = (
            {"account_id": {"$in": sorted(account_ids)}}
            if user_id is not None
            else {}
        )
        for record in await self.db["ag_exp_challenger_objects"].find(
            challenger_query
        ).to_list(length=None):
            record = clean_document(record)
            mapped = challenger_type_map.get(str(record.get("object_type")))
            if mapped is None:
                continue
            subject_type, stage = mapped
            payload = dict(record.get("payload") or {})
            account = account_map.get(str(record.get("account_id")), {})
            snapshot_id = str(record.get("snapshot_id") or payload.get("snapshot_id") or "")
            snapshot = snapshots.get(snapshot_id, {})
            status = str(payload.get("status") or payload.get("calculation_status") or "RECORDED")
            action = payload.get("action") or payload.get("action_candidate")
            source_version = (
                payload.get("strategy_version")
                or (payload.get("model_meta") or {}).get("model_version")
                or payload.get("consensus_policy_version")
                or payload.get("risk_policy_version")
            )
            evidence_refs = (
                list(payload.get("evidence_refs") or [])
                + list(payload.get("bullish_evidence") or [])
                + list(payload.get("bearish_evidence") or [])
            )
            lineage = {
                "experiment_id": str(record["experiment_id"]),
                "challenger_version_id": str(record["challenger_version_id"]),
                "baseline_champion_id": str(record["baseline_champion_id"]),
                "account_id": str(record["account_id"]),
                "assignment_id": str(record["assignment_id"]),
                "run_id": str(record["run_id"]),
                "run_mode": str(record.get("run_mode") or "PAPER_CHALLENGER"),
                "snapshot_id": snapshot_id,
                "config_hash": str(record["config_hash"]),
                "proposal_id": str(payload.get("proposal_id") or payload.get("quant_proposal_id") or ""),
                "plan_id": str(payload.get("plan_id") or ""),
                "review_id": str(payload.get("review_id") or ""),
                "consensus_id": str(payload.get("consensus_id") or ""),
                "risk_decision_id": str(payload.get("risk_decision_id") or ""),
            }
            drafts.append(
                self._draft(
                    subject_type=subject_type,
                    source=payload,
                    source_object_id=str(record["object_id"]),
                    source_object_version=(str(source_version) if source_version else None),
                    stage=stage,
                    status=status,
                    action=_status_action(status, action),
                    snapshot_id=snapshot_id,
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(account.get("user_id") or snapshot.get("user_id") or ""),
                    symbol=str(payload.get("symbol") or snapshot.get("symbol") or ""),
                    market=str(payload.get("market") or snapshot.get("market") or "CN"),
                    decision_trade_date=_as_date(
                        payload.get("trade_date") or snapshot.get("trade_date")
                    ),
                    candidate_id=payload.get("candidate_id"),
                    analysis_id=payload.get("analysis_id"),
                    entry_zone=payload.get("entry_zone"),
                    initial_position_pct=(
                        payload.get("approved_position_pct")
                        if stage == "HARD_RISK"
                        else payload.get("initial_position_pct")
                    ),
                    max_position_pct=(
                        payload.get("approved_position_pct")
                        if stage == "HARD_RISK"
                        else payload.get("max_position_pct")
                    ),
                    evidence_refs=evidence_refs,
                    lineage_ids=lineage,
                    selected_for_execution=(
                        status in {"TRIGGERED", "PROPOSE_TRADE", "CONFIRM", "RISK_ADJUST", "CONSENSUS_PASS", "PASS", "REDUCE"}
                    ),
                    actual_execution_exists=(
                        str(record["experiment_id"]) in challenger_executed
                    ),
                )
            )

        for benchmark in await self.db["ag_benchmark_execution_decisions"].find(
            {"account_id": {"$in": sorted(account_ids)}} if user_id is not None else {}
        ).to_list(length=None):
            benchmark = clean_document(benchmark)
            account = account_map.get(str(benchmark.get("account_id")), {})
            source_id = str(benchmark["source_object_id"])
            source = (
                next(
                    (
                        item
                        for item in drafts
                        if item["source_object_id"] == source_id
                    ),
                    None,
                )
                or {}
            )
            if not source:
                continue
            drafts.append(
                self._draft(
                    subject_type="BENCHMARK_DECISION",
                    source=benchmark,
                    source_object_id=str(benchmark["benchmark_decision_id"]),
                    source_object_version="benchmark-safety-v1",
                    stage="BENCHMARK_SAFETY",
                    status=str(benchmark["status"]),
                    action=_status_action(
                        str(benchmark["status"]), benchmark.get("action")
                    ),
                    snapshot_id=source["snapshot_id"],
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(account.get("user_id") or source["user_id"]),
                    symbol=source["symbol"],
                    market=source["market"],
                    decision_trade_date=source["decision_trade_date"],
                    candidate_id=source.get("candidate_id"),
                    analysis_id=source.get("analysis_id"),
                    initial_position_pct=benchmark.get("approved_position_pct"),
                    max_position_pct=benchmark.get("approved_position_pct"),
                    evidence_refs=[],
                    lineage_ids={
                        **source.get("lineage_ids", {}),
                        "benchmark_decision_id": str(
                            benchmark["benchmark_decision_id"]
                        ),
                        "account_id": str(benchmark["account_id"]),
                    },
                    selected_for_execution=benchmark.get("status")
                    in {"PASS", "REDUCE"},
                    actual_execution_exists=source_id in executed_source_ids,
                )
            )

        outbox_query = {"user_id": str(user_id)} if user_id is not None else {}
        for outbox in await self.db["ag_execution_outbox"].find(outbox_query).to_list(
            length=None
        ):
            outbox = clean_document(outbox)
            source = next(
                (
                    item
                    for item in drafts
                    if item["source_object_id"]
                    == str(outbox.get("source_object_id") or "")
                ),
                None,
            )
            # An outbox row without a traceable production decision is not
            # converted into a synthetic evaluation identity.
            if source is None:
                continue
            drafts.append(
                self._draft(
                    subject_type="EXECUTION_OUTBOX",
                    source=outbox,
                    source_object_id=str(outbox["outbox_event_id"]),
                    source_object_version=outbox.get("schema_version"),
                    stage="EXECUTION",
                    status=f"OUTBOX_{outbox['status']}",
                    action=source["action"],
                    snapshot_id=source["snapshot_id"],
                    snapshots=snapshots,
                    contexts=context_by_snapshot,
                    user_id=str(outbox.get("user_id") or source["user_id"]),
                    symbol=source["symbol"],
                    market=source["market"],
                    decision_trade_date=source["decision_trade_date"],
                    candidate_id=outbox.get("candidate_id")
                    or source.get("candidate_id"),
                    analysis_id=outbox.get("analysis_id")
                    or source.get("analysis_id"),
                    entry_zone=source.get("entry_zone"),
                    initial_position_pct=source.get("initial_position_pct"),
                    max_position_pct=source.get("max_position_pct"),
                    evidence_refs=source.get("evidence_refs", []),
                    lineage_ids={
                        **source.get("lineage_ids", {}),
                        "outbox_event_id": str(outbox["outbox_event_id"]),
                        "account_id": str(outbox.get("account_id") or ""),
                    },
                    selected_for_execution=True,
                    actual_execution_exists=str(outbox["source_object_id"])
                    in executed_source_ids,
                )
            )

        for intent in intents:
            source = next(
                (
                    item
                    for item in drafts
                    if item["source_object_id"] == str(intent["source_object_id"])
                ),
                None,
            )
            drafts.append(
                self._execution_draft(
                    subject_type="ORDER_INTENT",
                    source=intent,
                    source_object_id=str(intent["intent_id"]),
                    status="CREATED",
                    action=str(intent["original_action"]),
                    context=source,
                    snapshots=snapshots,
                    context_by_snapshot=context_by_snapshot,
                    account_map=account_map,
                    actual_execution_exists=str(intent["intent_id"])
                    in filled_intents,
                    lineage_ids={
                        "intent_id": str(intent["intent_id"]),
                        "proposal_id": str(intent.get("quant_proposal_id") or ""),
                        "plan_id": str(intent.get("plan_id") or ""),
                        "consensus_id": str(intent.get("consensus_id") or ""),
                        "risk_decision_id": str(intent.get("risk_decision_id") or ""),
                        "account_id": str(intent["account_id"]),
                        "experiment_id": str(intent.get("experiment_id") or ""),
                        "assignment_id": str(intent.get("assignment_id") or ""),
                        "challenger_version_id": str(intent.get("challenger_version_id") or ""),
                        "baseline_champion_id": str(intent.get("baseline_champion_id") or ""),
                        "run_mode": str(intent.get("run_mode") or ""),
                        "config_hash": str(intent.get("config_hash") or ""),
                    },
                )
            )

        for order in orders:
            intent = intent_map.get(str(order.get("intent_id")), {})
            drafts.append(
                self._execution_draft(
                    subject_type="PAPER_ORDER",
                    source=order,
                    source_object_id=str(order["order_id"]),
                    status=str(order["status"]),
                    action=str(order["original_action"]),
                    context=None,
                    snapshots=snapshots,
                    context_by_snapshot=context_by_snapshot,
                    account_map=account_map,
                    actual_execution_exists=any(
                        str(fill.get("order_id")) == str(order["order_id"])
                        for fill in fills
                    ),
                    lineage_ids={
                        "order_id": str(order["order_id"]),
                        "intent_id": str(order.get("intent_id") or ""),
                        "proposal_id": str(intent.get("quant_proposal_id") or ""),
                        "plan_id": str(intent.get("plan_id") or ""),
                        "risk_decision_id": str(
                            order.get("risk_decision_id")
                            or intent.get("risk_decision_id")
                            or ""
                        ),
                        "account_id": str(order["account_id"]),
                        "experiment_id": str(
                            order.get("experiment_id")
                            or intent.get("experiment_id")
                            or ""
                        ),
                        "assignment_id": str(
                            order.get("assignment_id")
                            or intent.get("assignment_id")
                            or ""
                        ),
                        "challenger_version_id": str(
                            order.get("challenger_version_id")
                            or intent.get("challenger_version_id")
                            or ""
                        ),
                        "baseline_champion_id": str(
                            order.get("baseline_champion_id")
                            or intent.get("baseline_champion_id")
                            or ""
                        ),
                        "run_mode": str(order.get("run_mode") or intent.get("run_mode") or ""),
                        "config_hash": str(order.get("config_hash") or intent.get("config_hash") or ""),
                    },
                    intent=intent,
                )
            )

        for fill in fills:
            order = order_map.get(str(fill.get("order_id")), {})
            intent = intent_map.get(str(order.get("intent_id")), {})
            lineage = {
                "fill_id": str(fill["fill_id"]),
                "order_id": str(fill["order_id"]),
                "intent_id": str(fill.get("intent_id") or ""),
                "proposal_id": str(intent.get("quant_proposal_id") or ""),
                "plan_id": str(intent.get("plan_id") or ""),
                "risk_decision_id": str(intent.get("risk_decision_id") or ""),
                "account_id": str(fill["account_id"]),
                "experiment_id": str(
                    fill.get("experiment_id")
                    or intent.get("experiment_id")
                    or ""
                ),
                "assignment_id": str(
                    fill.get("assignment_id")
                    or intent.get("assignment_id")
                    or ""
                ),
                "challenger_version_id": str(
                    fill.get("challenger_version_id")
                    or intent.get("challenger_version_id")
                    or ""
                ),
                "baseline_champion_id": str(
                    fill.get("baseline_champion_id")
                    or intent.get("baseline_champion_id")
                    or ""
                ),
                "run_mode": str(fill.get("run_mode") or intent.get("run_mode") or ""),
                "config_hash": str(fill.get("config_hash") or intent.get("config_hash") or ""),
                "fill_trade_date": str(fill["trade_date"]),
                "fill_price": str(fill["price"]),
                "fill_quantity": str(fill["quantity"]),
            }
            common = self._execution_draft(
                subject_type="PAPER_FILL",
                source=fill,
                source_object_id=str(fill["fill_id"]),
                status="FILLED",
                action=str(order.get("original_action") or fill.get("side")),
                context=None,
                snapshots=snapshots,
                context_by_snapshot=context_by_snapshot,
                account_map=account_map,
                actual_execution_exists=True,
                lineage_ids=lineage,
                intent=intent,
            )
            drafts.append(common)
            if fill.get("side") == "SELL":
                exit_draft = dict(common)
                exit_draft["subject_type"] = "POSITION_EXIT"
                exit_draft["decision_status"] = "POSITION_EXIT_FILLED"
                drafts.append(exit_draft)

        # Propagate actual execution through the immutable lineage rather than
        # only marking the object directly referenced by an OrderIntent.  A
        # TOP_CONFIRMED intent references RiskDecision, while the same fill is
        # also evidence that its consensus, review, plan and proposal reached
        # execution.
        executed_lineage_ids = {
            draft["source_object_id"]
            for draft in drafts
            if draft.get("actual_execution_exists")
        }
        changed = True
        while changed:
            changed = False
            for draft in drafts:
                if draft["source_object_id"] not in executed_lineage_ids:
                    continue
                for lineage_id in draft.get("lineage_ids", {}).values():
                    if lineage_id and lineage_id not in executed_lineage_ids:
                        executed_lineage_ids.add(lineage_id)
                        changed = True
        for draft in drafts:
            if draft["source_object_id"] in executed_lineage_ids:
                draft["actual_execution_exists"] = True

        subjects: list[EvaluationSubject] = []
        created_count = reused_count = 0
        seen: set[tuple[str, str]] = set()
        for draft in drafts:
            if (
                decision_trade_date_lte is not None
                and draft.get("decision_trade_date") is not None
                and draft["decision_trade_date"] > decision_trade_date_lte
            ):
                continue
            if (
                source_object_id is not None
                and draft["source_object_id"] != source_object_id
            ):
                continue
            key = (draft["subject_type"], draft["source_object_id"])
            if key in seen:
                continue
            seen.add(key)
            if not all(
                [
                    draft.get("user_id"),
                    draft.get("symbol"),
                    draft.get("market"),
                    draft.get("snapshot_id"),
                    draft.get("decision_trade_date"),
                    draft.get("decision_cutoff_at"),
                ]
            ):
                continue
            identity = (
                f"{draft['subject_type']}:{draft['source_object_id']}:"
                f"{self.version}"
            )
            subject_id = str(
                uuid5(NAMESPACE_URL, f"alphaguard:evaluation-subject:{identity}")
            )
            payload = {
                **draft,
                "subject_id": subject_id,
                "evaluation_version": self.version,
                "created_at": datetime.utcnow(),
            }
            payload["immutable_hash"] = evaluation_hash(
                payload,
                exclude={"subject_id", "immutable_hash", "created_at"},
            )
            subject = EvaluationSubject.model_validate(payload)
            stored, created = await self.repository.save_immutable(
                "subjects",
                subject,
                identity={
                    "subject_type": subject.subject_type,
                    "source_object_id": subject.source_object_id,
                    "evaluation_version": subject.evaluation_version,
                },
                hash_field="immutable_hash",
            )
            subjects.append(stored)
            created_count += int(created)
            reused_count += int(not created)
            await self.audit.record(
                (
                    "EVALUATION_SUBJECT_CREATED"
                    if created
                    else "EVALUATION_SUBJECT_REUSED"
                ),
                f"{subject.subject_type} evaluation subject "
                f"{'created' if created else 'reused'}",
                evaluation_job_id=evaluation_job_id,
                trace_id=trace_id,
                subject_id=subject.subject_id,
                source_object_id=subject.source_object_id,
                snapshot_id=subject.snapshot_id,
                analysis_id=subject.analysis_id,
                user_id=subject.user_id,
                symbol=subject.symbol,
                decision_trade_date=subject.decision_trade_date,
                input_hash=subject.immutable_hash,
            )
        return subjects, created_count, reused_count

    def _draft(
        self,
        *,
        subject_type: str,
        source: dict[str, Any],
        source_object_id: str,
        source_object_version: str | None,
        stage: str,
        status: str,
        action: str,
        snapshot_id: str,
        snapshots: dict[str, dict[str, Any]],
        contexts: dict[str, dict[str, Any]],
        user_id: str,
        symbol: str,
        market: str,
        decision_trade_date: date | None,
        candidate_id: str | None,
        analysis_id: str | None,
        entry_zone: Any = None,
        initial_position_pct: Any = None,
        max_position_pct: Any = None,
        evidence_refs: Iterable[Any] = (),
        lineage_ids: dict[str, str],
        selected_for_execution: bool,
        actual_execution_exists: bool,
    ) -> dict[str, Any]:
        snapshot = snapshots.get(snapshot_id, {})
        context = contexts.get(snapshot_id, {})
        cutoff_values = [
            _as_datetime(snapshot.get("price_cutoff_at")),
            _as_datetime(snapshot.get("news_cutoff_at")),
            _as_datetime(snapshot.get("announcement_cutoff_at")),
            _as_datetime(context.get("created_at")),
            _as_datetime(source.get("created_at")),
        ]
        cutoff = max((item for item in cutoff_values if item is not None), default=None)
        if entry_zone is not None:
            try:
                entry_zone = PriceRange.model_validate(entry_zone)
            except Exception:
                entry_zone = None
        return {
            "subject_type": subject_type,
            "source_object_id": source_object_id,
            "source_object_version": (
                str(source_object_version) if source_object_version is not None else None
            ),
            "user_id": user_id,
            "candidate_id": candidate_id,
            "symbol": symbol,
            "market": market,
            "snapshot_id": snapshot_id,
            "analysis_id": analysis_id,
            "decision_trade_date": _as_date(decision_trade_date),
            "decision_cutoff_at": cutoff,
            "action": action,
            "decision_stage": stage,
            "decision_status": status,
            "selected_for_execution": bool(selected_for_execution),
            "actual_execution_exists": bool(actual_execution_exists),
            "entry_zone": entry_zone,
            "initial_position_pct": _decimal(initial_position_pct),
            "max_position_pct": _decimal(max_position_pct),
            "evidence_refs": _evidence(evidence_refs),
            "lineage_ids": {
                key: str(value)
                for key, value in lineage_ids.items()
                if value is not None and str(value)
            },
        }

    def _execution_draft(
        self,
        *,
        subject_type: str,
        source: dict[str, Any],
        source_object_id: str,
        status: str,
        action: str,
        context: dict[str, Any] | None,
        snapshots: dict[str, dict[str, Any]],
        context_by_snapshot: dict[str, dict[str, Any]],
        account_map: dict[str, dict[str, Any]],
        actual_execution_exists: bool,
        lineage_ids: dict[str, str],
        intent: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        intent = intent or source
        snapshot_id = str(intent.get("snapshot_id") or "")
        context = context or context_by_snapshot.get(snapshot_id, {})
        account = account_map.get(str(source.get("account_id")), {})
        trade_date = (
            _as_date(context.get("trade_date"))
            or _as_date(source.get("trade_date"))
            or _as_date(intent.get("earliest_execute_at"))
        )
        entry_zone = None
        if intent.get("limit_price") is not None:
            entry_zone = {
                "lower": intent["limit_price"],
                "upper": intent["limit_price"],
            }
        return self._draft(
            subject_type=subject_type,
            source=source,
            source_object_id=source_object_id,
            source_object_version=(
                source.get("matching_engine_version")
                or intent.get("execution_policy_version")
                or source.get("schema_version")
            ),
            stage="EXECUTION",
            status=status,
            action=_status_action(status, action),
            snapshot_id=snapshot_id,
            snapshots=snapshots,
            contexts=context_by_snapshot,
            user_id=str(
                source.get("user_id")
                or intent.get("user_id")
                or account.get("user_id")
                or ""
            ),
            symbol=str(source.get("symbol") or intent.get("symbol") or ""),
            market=str(source.get("market") or intent.get("market") or "CN"),
            decision_trade_date=trade_date,
            candidate_id=source.get("candidate_id") or intent.get("candidate_id"),
            analysis_id=source.get("analysis_id") or intent.get("analysis_id"),
            entry_zone=entry_zone,
            evidence_refs=[],
            lineage_ids=lineage_ids,
            selected_for_execution=True,
            actual_execution_exists=actual_execution_exists,
        )
