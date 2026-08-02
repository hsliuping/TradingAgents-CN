"""Experiment-owned PAPER_CHALLENGER orchestration over existing engines."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import FactorEvidenceBundle
from app.schemas.alphaguard.decision import (
    DecisionContext,
    RevisionRequest,
    canonical_hash,
)
from app.schemas.alphaguard.quant import MarketRegimeResult, QuantTradeProposal
from app.services.alphaguard.consensus_engine import ConsensusEngine
from app.services.alphaguard.decision_context_builder import (
    MAX_EVIDENCE_REFS_PER_CATEGORY,
    NORMAL_QUANT_PROMPT_VERSION,
    TOP_QUANT_PROMPT_VERSION,
    _refs,
)
from app.services.alphaguard.experiment_component_adapters import (
    DeterministicExperimentAdapter,
)
from app.services.alphaguard.execution_outbox_service import ExecutionOutboxService
from app.services.alphaguard.hard_risk_engine import HardRiskEngine
from app.services.alphaguard.model_runtime_context import build_model_runtime_context
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.profiled_decision_model_runner import (
    ProfiledDecisionModelRunner,
)
from app.services.alphaguard.revision_service import REVISION_CONSTRAINTS
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.snapshot_data_resolver import (
    ResolvedSnapshotData,
    SnapshotDataResolver,
)
from app.services.alphaguard.snapshot_research_runtime import SnapshotResearchRuntime
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChallengerAssignment,
    ChallengerStageRecord,
    ExperimentOutputPair,
    PaperChallengerRun,
    experiment_hash,
)

from .experiment_audit_service import ExperimentAuditService
from .experiment_registry import ExperimentRegistry
from .experiment_repository import ExperimentRepository, experiment_document


TERMINAL_RUN_STATUSES = frozenset({"COMPLETED", "BLOCKED", "FAILED", "CANCELLED"})
MODEL_SUCCESS_STATUSES = frozenset(
    {"SUCCESS", "INSUFFICIENT_DATA", "DISABLED_NOT_REQUIRED"}
)


class ChallengerRuntimeError(RuntimeError):
    pass


class ChallengerModelExecutor(Protocol):
    async def prepare(
        self,
        *,
        context: DecisionContext,
        data: ResolvedSnapshotData,
        run: PaperChallengerRun,
    ) -> list[Any]: ...

    async def run_normal(
        self,
        *,
        context: DecisionContext,
        revision_request: RevisionRequest | None = None,
        original_plan: NormalTradePlan | None = None,
    ) -> NormalTradePlan: ...

    async def run_top(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
    ) -> TopReviewDecision: ...


class ExistingChallengerModelExecutor:
    """Reuse PR-010 research and model runners without decision DB writes."""

    def __init__(self, db):
        self.db = db
        self.runner: ProfiledDecisionModelRunner | None = None
        self.run_id: str | None = None

    async def prepare(
        self,
        *,
        context: DecisionContext,
        data: ResolvedSnapshotData,
        run: PaperChallengerRun,
    ) -> list[Any]:
        runtime_context = build_model_runtime_context(context, data)
        research_runtime = SnapshotResearchRuntime(self.db)
        research = await research_runtime.run(
            analysis_id=context.analysis_id,
            context=runtime_context,
            run_mode="PAPER_CHALLENGER",
        )
        research.append(
            await research_runtime.disabled_social_result(
                analysis_id=context.analysis_id,
                context=runtime_context,
            )
        )
        blocked = next(
            (item for item in research if item.status not in MODEL_SUCCESS_STATUSES),
            None,
        )
        if blocked is not None:
            raise ChallengerRuntimeError(
                f"RESEARCH_MODEL_PATH_FAILED:{blocked.agent_name}:{blocked.status}"
            )
        self.runner = await ProfiledDecisionModelRunner.create(
            db=self.db,
            run_mode="PAPER_CHALLENGER",
            automated_execution_allowed=True,
            model_runtime_context_hash=runtime_context.context_hash,
            research_results=[item.model_dump(mode="json") for item in research],
            model_call_analysis_id=context.analysis_id,
        )
        self.run_id = run.run_id
        return research

    def _ready(self) -> ProfiledDecisionModelRunner:
        if self.runner is None:
            raise ChallengerRuntimeError("model executor was not prepared")
        return self.runner

    async def run_normal(
        self,
        *,
        context: DecisionContext,
        revision_request: RevisionRequest | None = None,
        original_plan: NormalTradePlan | None = None,
    ) -> NormalTradePlan:
        return await self._ready().run_normal(
            context=context,
            attempt_number=1,
            trace_id=self.run_id,
            revision_request=revision_request,
            original_plan=original_plan,
        )

    async def run_top(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
    ) -> TopReviewDecision:
        return await self._ready().run_top(
            context=context,
            plan=plan,
            risk_policy_summary=risk_policy_summary,
            attempt_number=1,
            trace_id=self.run_id,
        )


class PaperChallengerRuntimeService:
    """Run one active Challenger opportunity without mutating Champion facts."""

    def __init__(
        self,
        db,
        *,
        model_executor: ChallengerModelExecutor | None = None,
        snapshot_resolver: SnapshotDataResolver | None = None,
        component_adapter: DeterministicExperimentAdapter | None = None,
    ):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.registry = ExperimentRegistry(db)
        self.accounts = PaperAccountService(db)
        self.resolver = snapshot_resolver or SnapshotDataResolver(db)
        self.adapter = component_adapter or DeterministicExperimentAdapter()
        self.model_executor = model_executor
        self.consensus = ConsensusEngine()
        self.hard_risk = HardRiskEngine()
        self.risk_policies = RiskPolicyRegistry(db)
        self.outbox = ExecutionOutboxService(db)
        self.audit = ExperimentAuditService(db)

    async def run(
        self,
        *,
        experiment_id: str,
        snapshot_id: str,
        trading_date: date,
        candidate_id: str | None = None,
        retry_failed: bool = False,
        now: datetime | None = None,
    ) -> tuple[PaperChallengerRun, bool]:
        now = now or datetime.utcnow()
        definition = await self.registry.get(experiment_id)
        assignment = await self._active_assignment(experiment_id)
        self._validate_definition(definition, assignment, trading_date)
        data = await self.resolver.resolve(snapshot_id, user_id=assignment.user_id)
        self._validate_snapshot(data, assignment, trading_date)
        task_payload = {
            "job_type": "PAPER_CHALLENGER",
            "experiment_id": experiment_id,
            "challenger_version_id": assignment.challenger_version_id,
            "trading_date": trading_date,
            "candidate_id": candidate_id,
            "snapshot_id": snapshot_id,
            "config_hash": assignment.config_hash,
        }
        task_identity = experiment_hash(task_payload)
        existing = clean_document(
            await self.db["ag_exp_challenger_runs"].find_one(
                {"task_identity": task_identity}
            )
        )
        if existing is not None:
            stored = PaperChallengerRun.model_validate(existing)
            if stored.status == "FAILED" and retry_failed:
                run = stored.model_copy(
                    update={
                        "status": "RUNNING",
                        "failure_code": None,
                        "result_hash": None,
                        "completed_at": None,
                        "updated_at": now,
                    }
                )
                result = await self.db["ag_exp_challenger_runs"].replace_one(
                    {
                        "run_id": stored.run_id,
                        "status": "FAILED",
                        "result_hash": stored.result_hash,
                    },
                    experiment_document(run),
                )
                if result.matched_count != 1:
                    raise ChallengerRuntimeError(
                        "PAPER_CHALLENGER_RETRY_CONFLICT"
                    )
            elif stored.status in TERMINAL_RUN_STATUSES:
                return stored, True
            else:
                raise ChallengerRuntimeError(
                    "PAPER_CHALLENGER_RUN_ALREADY_IN_PROGRESS"
                )
        else:
            run = PaperChallengerRun(
                run_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:paper-challenger:{task_identity}",
                    )
                ),
                task_identity=task_identity,
                experiment_id=experiment_id,
                challenger_version_id=str(assignment.challenger_version_id),
                baseline_champion_id=str(assignment.baseline_champion_id),
                baseline_champion_version=str(
                    assignment.baseline_champion_version
                ),
                assignment_id=assignment.assignment_id,
                account_id=assignment.account_id,
                user_id=assignment.user_id,
                symbol=data.snapshot.symbol,
                trading_date=trading_date,
                candidate_id=candidate_id,
                snapshot_id=snapshot_id,
                snapshot_hash=data.snapshot.immutable_hash,
                config_hash=str(assignment.config_hash),
                automated_execution_allowed=True,
                validation_only=assignment.validation_only,
                promotion_eligible=assignment.promotion_eligible,
                status="RUNNING",
                created_at=now,
                updated_at=now,
            )
            await self.db["ag_exp_challenger_runs"].insert_one(
                experiment_document(run)
            )
        try:
            run = await self._execute(
                run,
                definition,
                assignment,
                data,
                decision_at=run.created_at,
                completed_at=now,
            )
        except Exception as exc:
            current = clean_document(
                await self.db["ag_exp_challenger_runs"].find_one(
                    {"run_id": run.run_id}
                )
            )
            if current is not None:
                run = PaperChallengerRun.model_validate(current)
            run = await self._finish(
                run,
                status="FAILED",
                terminal_stage=run.terminal_stage or "RUNTIME",
                failure_code=type(exc).__name__,
                now=now,
            )
            await self.audit.record(
                "CHALLENGER_RUN_FAILED",
                f"{type(exc).__name__}: {str(exc)[:300]}",
                experiment_id=experiment_id,
                assignment_id=assignment.assignment_id,
                run_id=run.run_id,
                user_id=assignment.user_id,
                market=assignment.market,
            )
            raise
        return run, False

    async def _execute(
        self,
        run,
        definition,
        assignment,
        data,
        *,
        decision_at,
        completed_at,
    ):
        now = decision_at
        baseline = await self.registry.component_version(
            definition.baseline_version_ref
        )
        challenger = await self.registry.component_version(
            definition.challenger_version_ref
        )
        champion_output, challenger_output, difference = self.adapter.run_pair(
            data, baseline, challenger
        )
        bundle = FactorEvidenceBundle.model_validate(
            challenger_output["factor_bundle"]
        )
        regime = MarketRegimeResult.model_validate(
            challenger_output["market_regime"]
        )
        proposals = [
            QuantTradeProposal.model_validate(item)
            for item in challenger_output["quant_proposals"]
        ]
        for factor in bundle.results:
            run = await self._stage(run, "FACTOR_RESULT", factor.result_id, factor)
        run = await self._stage(
            run, "REGIME_RESULT", regime.regime_result_id, regime
        )
        for proposal in proposals:
            run = await self._stage(
                run, "QUANT_PROPOSAL", proposal.proposal_id, proposal
            )
        eligible = sorted(
            (
                item
                for item in proposals
                if item.status == "TRIGGERED"
                and item.action_candidate in {"BUY", "SELL", "REDUCE"}
            ),
            key=lambda item: (
                -float(item.initial_position_pct),
                item.strategy_id,
                item.proposal_id,
            ),
        )
        if not eligible:
            return await self._finish(
                run,
                status="BLOCKED",
                terminal_stage="QUANT_PROPOSAL",
                failure_code="NO_TRIGGERED_PROPOSAL",
                now=completed_at,
            )
        proposal = eligible[0]
        challenger_data = await self._with_challenger_account(
            data, assignment, run.trading_date, now=now
        )
        context = self._decision_context(
            run, proposal, bundle, regime, challenger_data, now=now
        )
        run = await self._stage(
            run, "DECISION_CONTEXT", context.decision_context_id, context
        )
        executor = self.model_executor or ExistingChallengerModelExecutor(self.db)
        research = await executor.prepare(
            context=context, data=challenger_data, run=run
        )
        for item in research:
            payload = self._payload(item)
            object_id = str(
                payload.get("research_result_id")
                or payload.get("result_id")
                or experiment_hash(payload)
            )
            run = await self._stage(run, "RESEARCH_RESULT", object_id, payload)
        plan = await executor.run_normal(context=context)
        run = await self._stage(run, "NORMAL_PLAN", plan.plan_id, plan)
        if plan.status != "PROPOSE_TRADE":
            return await self._finish(
                run,
                status="BLOCKED",
                terminal_stage="NORMAL_PLAN",
                failure_code=f"NORMAL_{plan.status}",
                now=completed_at,
            )
        policy = await self.risk_policies.get_active()
        policy_summary = policy.model_dump(
            mode="json", exclude={"created_at", "config_hash"}
        )
        review = await executor.run_top(
            context=context, plan=plan, risk_policy_summary=policy_summary
        )
        run = await self._stage(run, "TOP_REVIEW", review.review_id, review)
        consensus = self.consensus.evaluate(
            context=context, plan=plan, review=review, now=now
        )
        if consensus.status == "CONSENSUS_REVISE":
            revision = self._revision_request(context, plan, review, now=now)
            run = await self._stage(
                run,
                "REVISION_REQUEST",
                revision.revision_request_id,
                revision,
            )
            plan = await executor.run_normal(
                context=context,
                revision_request=revision,
                original_plan=plan,
            )
            run = await self._stage(run, "NORMAL_PLAN", plan.plan_id, plan)
            if plan.status == "PROPOSE_TRADE":
                review = await executor.run_top(
                    context=context,
                    plan=plan,
                    risk_policy_summary=policy_summary,
                )
                run = await self._stage(
                    run, "TOP_REVIEW", review.review_id, review
                )
                consensus = self.consensus.evaluate(
                    context=context, plan=plan, review=review, now=now
                )
        run = await self._stage(
            run,
            "CONSENSUS_DECISION",
            consensus.consensus_id,
            consensus,
        )
        if consensus.status != "CONSENSUS_PASS":
            return await self._finish(
                run,
                status="BLOCKED",
                terminal_stage="CONSENSUS_DECISION",
                failure_code=consensus.status,
                now=completed_at,
            )
        risk = self.hard_risk.evaluate(
            data=challenger_data,
            context=context,
            consensus=consensus,
            policy=policy,
            account_id=assignment.account_id,
            now=now,
        )
        run = await self._stage(
            run, "HARD_RISK_DECISION", risk.risk_decision_id, risk
        )
        if risk.status not in {"PASS", "REDUCE"}:
            return await self._finish(
                run,
                status="BLOCKED",
                terminal_stage="HARD_RISK_DECISION",
                failure_code=f"HARD_RISK_{risk.status}",
                now=completed_at,
            )
        output = await self._save_output(
            run=run,
            definition=definition,
            data=challenger_data,
            champion_output=champion_output,
            challenger_output={
                **challenger_output,
                "decision_context": context.model_dump(mode="json"),
                "normal_trade_plan": plan.model_dump(mode="json"),
                "top_review_decision": review.model_dump(mode="json"),
                "consensus_decision": consensus.model_dump(mode="json"),
                "risk_decision": risk.model_dump(mode="json"),
            },
            difference=difference,
            now=completed_at,
        )
        event = await self.outbox.enqueue(
            event_type="CREATE_CHALLENGER_INTENT",
            source_object_id=output.output_id,
            user_id=assignment.user_id,
            account_id=assignment.account_id,
            analysis_id=context.analysis_id,
            candidate_id=run.candidate_id,
            snapshot_id=run.snapshot_id,
            experiment_id=run.experiment_id,
            assignment_id=run.assignment_id,
            challenger_version_id=run.challenger_version_id,
            baseline_champion_id=run.baseline_champion_id,
            config_hash=run.config_hash,
            run_mode="PAPER_CHALLENGER",
            now=now,
        )
        run = await self._stage(
            run, "EXECUTION_OUTBOX", event.outbox_event_id, event
        )
        run = run.model_copy(update={"outbox_event_id": event.outbox_event_id})
        return await self._finish(
            run,
            status="COMPLETED",
            terminal_stage="EXECUTION_OUTBOX",
            failure_code=None,
            now=completed_at,
        )

    async def _active_assignment(self, experiment_id: str) -> ChallengerAssignment:
        raw = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {"experiment_id": experiment_id, "status": "ACTIVE"}
            )
        )
        if raw is None:
            raise ChallengerRuntimeError("ACTIVE_CHALLENGER_ASSIGNMENT_REQUIRED")
        return ChallengerAssignment.model_validate(raw)

    @staticmethod
    def _validate_definition(definition, assignment, trading_date: date) -> None:
        if definition.status != "CHALLENGER":
            raise ChallengerRuntimeError("EXPERIMENT_NOT_CHALLENGER")
        required = (
            assignment.challenger_version_id,
            assignment.baseline_champion_id,
            assignment.baseline_champion_version,
            assignment.config_hash,
        )
        if not all(required):
            raise ChallengerRuntimeError("CHALLENGER_IDENTITY_INCOMPLETE")
        if assignment.activation_trade_date > trading_date:
            raise ChallengerRuntimeError("CHALLENGER_NOT_YET_ACTIVE")
        if assignment.challenger_version_id != definition.challenger_version_ref:
            raise ChallengerRuntimeError("CHALLENGER_VERSION_MISMATCH")
        expected_config = definition.config_hash or definition.immutable_definition_hash
        if assignment.config_hash != expected_config:
            raise ChallengerRuntimeError("CHALLENGER_CONFIG_HASH_MISMATCH")

    @staticmethod
    def _validate_snapshot(data, assignment, trading_date: date) -> None:
        snapshot = data.snapshot
        if snapshot.user_id != assignment.user_id or snapshot.market != assignment.market:
            raise ChallengerRuntimeError("SNAPSHOT_ASSIGNMENT_IDENTITY_MISMATCH")
        if snapshot.trade_date != trading_date:
            raise ChallengerRuntimeError("SNAPSHOT_TRADING_DATE_MISMATCH")
        if snapshot.schema_version not in {
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
        } or snapshot.evidence_contract_status != "COMPLETE":
            raise ChallengerRuntimeError("SNAPSHOT_EVIDENCE_CONTRACT_INCOMPLETE")
        if snapshot.run_mode not in {None, "ACTUAL_PRODUCTION"}:
            raise ChallengerRuntimeError("NON_PRODUCTION_SNAPSHOT_BLOCKED")

    async def _with_challenger_account(self, data, assignment, trading_date, *, now):
        account = await self.accounts.get_account(
            assignment.account_id, user_id=assignment.user_id
        )
        if account is None or account.account_type != "PAPER_CHALLENGER":
            raise ChallengerRuntimeError("PAPER_CHALLENGER_ACCOUNT_MISSING")
        if account.status != "ACTIVE":
            raise ChallengerRuntimeError("PAPER_CHALLENGER_ACCOUNT_NOT_ACTIVE")
        account_snapshot = await self.accounts.create_daily_snapshot(
            account.account_id, trading_date, now=now
        )
        position_rows = [
            clean_document(item)
            for item in await self.db["ag_paper_positions"].find(
                {"account_id": account.account_id, "quantity": {"$gt": 0}}
            ).to_list(length=None)
        ]
        order_rows = [
            clean_document(item)
            for item in await self.db["ag_paper_orders"].find(
                {"account_id": account.account_id}
            ).to_list(length=None)
        ]
        account_ref = f"paper_account_snapshot:{account_snapshot.account_snapshot_id}"
        account_evidence = {
            "_reference": account_ref,
            "account_id": account.account_id,
            "user_id": account.user_id,
            "market": account.market,
            "currency": account.currency,
            "status": account.status,
            "cash": {"CNY": account_snapshot.cash_available},
            "equity": {"CNY": account_snapshot.total_equity},
            "total_exposure_pct": account_snapshot.gross_exposure_pct,
            "industry_exposure_pct": {},
            "new_positions_today": 0,
            "active_orders_complete": True,
            "portfolio_empty_verified": not position_rows,
            "input_hash": account_snapshot.input_hash,
            "created_at": account_snapshot.created_at,
        }
        positions = []
        position_refs = []
        for item in position_rows:
            reference = f"paper_position:{item['position_id']}"
            position_refs.append(reference)
            positions.append(
                {
                    **item,
                    "_reference": reference,
                    "available_qty": item.get("available_quantity", 0),
                }
            )
        orders = []
        order_refs = []
        for item in order_rows:
            reference = f"paper_order:{item['order_id']}"
            order_refs.append(reference)
            orders.append({**item, "_reference": reference})
        refs = sorted(set(data.input_refs + [account_ref] + position_refs + order_refs))
        return data.model_copy(
            update={
                "accounts": [account_evidence],
                "positions": positions,
                "portfolio_positions": positions,
                "orders": orders,
                "input_refs": refs,
                "input_hash": experiment_hash(
                    {
                        "snapshot_input_hash": data.input_hash,
                        "account_snapshot_hash": account_snapshot.input_hash,
                        "positions": position_rows,
                        "orders": order_rows,
                    }
                ),
            }
        )

    @staticmethod
    def _decision_context(run, proposal, bundle, regime, data, *, now):
        analysis_id = str(uuid5(NAMESPACE_URL, f"alphaguard:{run.run_id}:analysis"))
        missing = list(data.snapshot.data_quality.missing_fields)
        payload = {
            "analysis_id": analysis_id,
            "user_id": run.user_id,
            "candidate_id": run.candidate_id,
            "symbol": run.symbol,
            "market": run.market,
            "trade_date": run.trading_date,
            "snapshot_id": run.snapshot_id,
            "quant_proposal_id": proposal.proposal_id,
            "strategy_id": proposal.strategy_id,
            "strategy_version": proposal.strategy_version,
            "factor_set_version": proposal.factor_set_version,
            "regime_result_id": proposal.regime_result_id,
            "quant_proposal": proposal,
            "factor_summary": proposal.factor_summary,
            "factor_result_ids": sorted(proposal.factor_result_ids),
            "market_regime": regime,
            "price_evidence": sorted(
                _refs(data.prices, "price")
                + _refs(data.instruments, "instrument")
                + _refs(data.trading_status, "trading_status")
                + _refs(data.trading_calendar, "trading_calendar"),
                key=lambda item: item.evidence_id,
            )[:MAX_EVIDENCE_REFS_PER_CATEGORY],
            "financial_evidence": _refs(data.financials + data.cashflows, "financial"),
            "news_evidence": _refs(data.news, "news"),
            "announcement_evidence": _refs(
                data.announcements + data.dividends + data.corporate_actions,
                "announcement",
            ),
            "account_evidence": _refs(data.accounts, "account"),
            "portfolio_evidence": _refs(
                data.positions + data.portfolio_positions + data.orders,
                "portfolio",
            ),
            "data_quality_status": data.snapshot.data_quality.status,
            "risk_flags": sorted(set(proposal.risk_flags)),
            "missing_evidence": sorted(set(missing)),
            "normal_prompt_version": NORMAL_QUANT_PROMPT_VERSION,
            "top_prompt_version": TOP_QUANT_PROMPT_VERSION,
            "created_at": now,
            "schema_version": "decision-context-v1",
        }
        draft = DecisionContext.model_construct(
            decision_context_id="pending", context_hash="0" * 64, **payload
        )
        context_hash = canonical_hash(
            draft,
            exclude={"decision_context_id", "context_hash", "created_at"},
        )
        payload["context_hash"] = context_hash
        payload["decision_context_id"] = str(
            uuid5(NAMESPACE_URL, f"alphaguard-context:{context_hash}")
        )
        return DecisionContext.model_validate(payload)

    @staticmethod
    def _revision_request(context, plan, review, *, now):
        identity = (
            f"{context.analysis_id}:{plan.plan_id}:{review.review_id}:"
            "revision-round-1"
        )
        return RevisionRequest(
            revision_request_id=str(uuid5(NAMESPACE_URL, identity)),
            analysis_id=context.analysis_id,
            snapshot_id=plan.snapshot_id,
            original_plan_id=plan.plan_id,
            review_id=review.review_id,
            requested_changes=review.material_change_fields,
            material_change_fields=review.material_change_fields,
            risk_findings=review.risk_findings,
            constraints=REVISION_CONSTRAINTS,
            created_at=now,
        )

    async def _save_output(
        self,
        *,
        run,
        definition,
        data,
        champion_output,
        challenger_output,
        difference,
        now,
    ):
        output_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:challenger-output:{run.run_id}")
        )
        payload = {
            "experiment_id": run.experiment_id,
            "run_id": run.run_id,
            "run_type": "PAPER_CHALLENGER",
            "snapshot_id": run.snapshot_id,
            "symbol": run.symbol,
            "market": run.market,
            "trade_date": run.trading_date,
            "decision_cutoff_at": data.snapshot.price_cutoff_at,
            "baseline_version_ref": definition.baseline_version_ref,
            "challenger_version_ref": definition.challenger_version_ref,
            "fixed_version_refs": {
                "snapshot_hash": data.snapshot.immutable_hash,
                "config_hash": run.config_hash,
                "baseline_champion": run.baseline_champion_version,
            },
            "champion_output": champion_output,
            "challenger_output": challenger_output,
            "difference": difference,
            "comparable": True,
            "incomparability_reasons": [],
            "decision_input_refs": sorted(data.input_refs),
            "evaluation_label_ids": [],
        }
        output = ExperimentOutputPair(
            output_id=output_id,
            input_hash=experiment_hash(
                {
                    "task_identity": run.task_identity,
                    "snapshot_hash": run.snapshot_hash,
                    "account_id": run.account_id,
                }
            ),
            result_hash=experiment_hash(payload),
            created_at=now,
            **payload,
        )
        stored, _ = await self.repository.save_immutable(
            "shadow_outputs",
            output,
            identity={"output_id": output.output_id},
            hash_field="result_hash",
        )
        return stored

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return dict(value)

    async def _stage(self, run, object_type, object_id, value):
        payload = self._payload(value)
        payload_hash = experiment_hash(payload)
        record = ChallengerStageRecord(
            record_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:challenger-stage:{run.run_id}:"
                    f"{object_type}:{object_id}",
                )
            ),
            object_type=object_type,
            object_id=str(object_id),
            experiment_id=run.experiment_id,
            challenger_version_id=run.challenger_version_id,
            baseline_champion_id=run.baseline_champion_id,
            account_id=run.account_id,
            assignment_id=run.assignment_id,
            run_id=run.run_id,
            snapshot_id=run.snapshot_id,
            config_hash=run.config_hash,
            payload=payload,
            payload_hash=payload_hash,
            created_at=run.created_at,
        )
        stored, _ = await self.repository.save_immutable(
            "challenger_objects",
            record,
            identity={"record_id": record.record_id},
            hash_field="payload_hash",
        )
        if stored.record_id in run.stage_record_ids:
            return run
        updated = run.model_copy(
            update={
                "stage_record_ids": [*run.stage_record_ids, stored.record_id],
                "terminal_stage": object_type,
                "updated_at": datetime.utcnow(),
            }
        )
        await self.db["ag_exp_challenger_runs"].replace_one(
            {"run_id": run.run_id, "status": "RUNNING"},
            experiment_document(updated),
        )
        return updated

    async def _finish(
        self,
        run,
        *,
        status,
        terminal_stage,
        failure_code,
        now,
    ):
        result_hash = experiment_hash(
            {
                "run_id": run.run_id,
                "task_identity": run.task_identity,
                "stage_record_ids": run.stage_record_ids,
                "terminal_stage": terminal_stage,
                "failure_code": failure_code,
                "outbox_event_id": run.outbox_event_id,
            }
        )
        updated = run.model_copy(
            update={
                "status": status,
                "terminal_stage": terminal_stage,
                "failure_code": failure_code,
                "result_hash": result_hash,
                "updated_at": now,
                "completed_at": now,
            }
        )
        await self.db["ag_exp_challenger_runs"].replace_one(
            {"run_id": run.run_id}, experiment_document(updated)
        )
        return updated
