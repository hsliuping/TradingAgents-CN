"""Human-only PromotionRequest/Approval and recoverable PromotionSaga."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.services.alphaguard.champion_resolver import (
    ChampionResolver,
    assignment_hash,
)
from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.promotion_policy_service import (
    PromotionPolicyService,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChampionAssignment,
    ChampionAssignmentHistory,
    ChampionComparisonReport,
    ExperimentRiskReview,
    PromotionApproval,
    PromotionRequest,
    PromotionSaga,
    experiment_hash,
)


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def promotion_request_hash(value) -> str:
    return experiment_hash(
        value,
        exclude={"request_hash", "status", "schema_version"},
    )


class ChampionPromotionService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.registry = ExperimentRegistry(db)
        self.policies = PromotionPolicyService(db)
        self.resolver = ChampionResolver(db)
        self.calendar = PaperTradingCalendarService(db)
        self.audit = ExperimentAuditService(db)

    async def create_request(
        self,
        experiment_id: str,
        *,
        comparison_report_id: str,
        risk_review_id: str,
        requested_by: str,
        effective_from_trade_date: date,
        now: datetime | None = None,
    ) -> PromotionRequest:
        now = now or datetime.utcnow()
        definition = await self.registry.get(experiment_id)
        if (
            definition.status != "CHALLENGER"
            or not definition.promotion_eligible
            or definition.experiment_mode != "UNIVARIATE"
        ):
            raise ValueError("experiment is not eligible CHALLENGER")
        comparison_raw = await self.repository.get(
            "comparison_reports",
            {"comparison_report_id": comparison_report_id},
        )
        review_raw = await self.repository.get(
            "risk_reviews", {"review_id": risk_review_id}
        )
        if comparison_raw is None or review_raw is None:
            raise LookupError("comparison and risk review are required")
        comparison = ChampionComparisonReport.model_validate(comparison_raw)
        review = ExperimentRiskReview.model_validate(review_raw)
        if (
            comparison.experiment_id != experiment_id
            or review.experiment_id != experiment_id
            or review.comparison_report_id != comparison_report_id
        ):
            raise ValueError("promotion evidence identity mismatch")
        if review.status != "READY_FOR_HUMAN_REVIEW":
            raise ValueError("top experiment risk review did not authorize human review")
        policy = await self.policies.get(definition.promotion_policy_version)
        failures = self.policies.check_report(policy, comparison)
        max_age = policy.stability_thresholds.get("comparison_max_age_days")
        if max_age is not None and (
            _utc(now) - _utc(comparison.created_at)
        ).days > int(max_age):
            failures.append("comparison_expired")
        if failures:
            raise ValueError(
                f"PromotionPolicy failed: {sorted(set(failures))}"
            )
        if not await self.calendar.is_open_date(effective_from_trade_date):
            raise ValueError("Champion effective date must be an open trade date")
        slot_id = (
            f"{definition.component_type}:"
            f"{definition.component_key}:{definition.market}"
        )
        current_raw = await self.repository.get(
            "champion_assignments", {"champion_slot_id": slot_id}
        )
        if current_raw is None:
            raise LookupError("current ChampionAssignment does not exist")
        current = ChampionAssignment.model_validate(current_raw)
        if current.current_version_ref != definition.baseline_version_ref:
            raise ExperimentIntegrityConflict(
                "current Champion differs from experiment baseline"
            )
        current_component = await self.registry.component_version(
            current.current_version_ref
        )
        proposed_component = await self.registry.component_version(
            definition.challenger_version_ref
        )
        required_text = (
            f"PROMOTE {experiment_id} TO {definition.challenger_version_ref}"
        )
        payload = {
            "promotion_request_id": str(uuid4()),
            "experiment_id": experiment_id,
            "comparison_report_id": comparison_report_id,
            "risk_review_id": risk_review_id,
            "requested_by": str(requested_by),
            "requested_at": now,
            "target_champion_slot_id": slot_id,
            "current_champion_version_ref": current.current_version_ref,
            "proposed_champion_version_ref": definition.challenger_version_ref,
            "current_champion_hash": current_component.payload_hash,
            "proposed_champion_hash": proposed_component.payload_hash,
            "promotion_policy_version": policy.policy_version,
            "effective_from_trade_date": effective_from_trade_date,
            "policy_check_status": "PASS",
            "failed_policy_rules": [],
            "required_confirmation_text": required_text,
            "status": "PENDING_APPROVAL",
        }
        payload["request_hash"] = promotion_request_hash(payload)
        request = PromotionRequest.model_validate(payload)
        await self.db["ag_exp_promotion_requests"].insert_one(
            experiment_document(request)
        )
        await self.audit.record(
            "PROMOTION_REQUEST_CREATED",
            "human approval is still required; no Champion pointer changed",
            experiment_id=experiment_id,
            comparison_report_id=comparison_report_id,
            risk_review_id=risk_review_id,
            promotion_request_id=request.promotion_request_id,
            champion_slot_id=slot_id,
            baseline_version_ref=current.current_version_ref,
            challenger_version_ref=definition.challenger_version_ref,
            current_champion_version_ref=current.current_version_ref,
            user_id=definition.user_id,
            market=definition.market,
            input_hash=request.request_hash,
        )
        return request

    async def reject_request(
        self,
        request_id: str,
        *,
        rejected_by: str,
        reason: str,
    ) -> PromotionRequest:
        raw = await self.repository.get(
            "promotion_requests", {"promotion_request_id": request_id}
        )
        if raw is None:
            raise LookupError("PromotionRequest does not exist")
        request = PromotionRequest.model_validate(raw)
        if request.status == "REJECTED":
            return request
        if request.status != "PENDING_APPROVAL":
            raise ValueError("only pending PromotionRequest can be rejected")
        updated = request.model_copy(update={"status": "REJECTED"})
        await self.db["ag_exp_promotion_requests"].replace_one(
            {
                "promotion_request_id": request_id,
                "status": "PENDING_APPROVAL",
            },
            experiment_document(updated),
        )
        await self.audit.record(
            "PROMOTION_REQUEST_REJECTED",
            f"{reason}; rejected_by={rejected_by}",
            experiment_id=request.experiment_id,
            promotion_request_id=request_id,
            champion_slot_id=request.target_champion_slot_id,
            input_hash=request.request_hash,
        )
        return updated

    async def approve_request(
        self,
        request_id: str,
        *,
        approved_by: str,
        decision_reason: str,
        confirmation_text: str,
        current_champion_hash: str,
        proposed_champion_hash: str,
        now: datetime | None = None,
    ) -> tuple[PromotionApproval, PromotionSaga]:
        now = now or datetime.utcnow()
        raw = await self.repository.get(
            "promotion_requests", {"promotion_request_id": request_id}
        )
        if raw is None:
            raise LookupError("PromotionRequest does not exist")
        request = PromotionRequest.model_validate(raw)
        existing_approval = await self.repository.get(
            "promotion_approvals", {"promotion_request_id": request_id}
        )
        if existing_approval:
            approval = PromotionApproval.model_validate(existing_approval)
            saga_raw = await self.repository.get(
                "promotion_sagas", {"promotion_request_id": request_id}
            )
            if saga_raw is None:
                raise ExperimentIntegrityConflict(
                    "approval exists without PromotionSaga"
                )
            return approval, PromotionSaga.model_validate(saga_raw)
        if request.status != "PENDING_APPROVAL":
            raise ValueError("PromotionRequest is not pending approval")
        if confirmation_text != request.required_confirmation_text:
            raise ValueError("promotion confirmation text mismatch")
        if (
            current_champion_hash != request.current_champion_hash
            or proposed_champion_hash != request.proposed_champion_hash
        ):
            raise ValueError("confirmed Champion hashes do not match request")
        current_raw = await self.repository.get(
            "champion_assignments",
            {"champion_slot_id": request.target_champion_slot_id},
        )
        if current_raw is None:
            raise LookupError("current ChampionAssignment does not exist")
        current = ChampionAssignment.model_validate(current_raw)
        current_component = await self.registry.component_version(
            current.current_version_ref
        )
        proposed_component = await self.registry.component_version(
            request.proposed_champion_version_ref
        )
        if (
            current.current_version_ref
            != request.current_champion_version_ref
            or current_component.payload_hash != current_champion_hash
            or proposed_component.payload_hash != proposed_champion_hash
        ):
            raise ExperimentIntegrityConflict(
                "Champion or Challenger changed before approval"
            )
        definition = await self.registry.get(request.experiment_id)
        if (
            definition.status != "CHALLENGER"
            or definition.promotion_policy_version
            != request.promotion_policy_version
        ):
            raise ValueError("experiment or locked policy changed")
        comparison_raw = await self.repository.get(
            "comparison_reports",
            {"comparison_report_id": request.comparison_report_id},
        )
        review_raw = await self.repository.get(
            "risk_reviews", {"review_id": request.risk_review_id}
        )
        comparison = ChampionComparisonReport.model_validate(comparison_raw)
        review = ExperimentRiskReview.model_validate(review_raw)
        policy = await self.policies.get(request.promotion_policy_version)
        if (
            review.status != "READY_FOR_HUMAN_REVIEW"
            or self.policies.check_report(policy, comparison)
        ):
            raise ValueError("promotion evidence is no longer valid")
        approval = PromotionApproval(
            approval_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:promotion-approval:{request_id}",
                )
            ),
            promotion_request_id=request_id,
            approved=True,
            approved_by=str(approved_by),
            decision_reason=decision_reason,
            confirmation_text=confirmation_text,
            current_champion_hash_confirmed=current_champion_hash,
            proposed_champion_hash_confirmed=proposed_champion_hash,
            approved_at=now,
        )
        await self.db["ag_exp_promotion_approvals"].insert_one(
            experiment_document(approval)
        )
        approved_request = request.model_copy(update={"status": "APPROVED"})
        await self.db["ag_exp_promotion_requests"].replace_one(
            {
                "promotion_request_id": request_id,
                "status": "PENDING_APPROVAL",
            },
            experiment_document(approved_request),
        )
        await self.audit.record(
            "PROMOTION_REQUEST_APPROVED",
            f"explicit administrator approval by {approved_by}",
            experiment_id=request.experiment_id,
            promotion_request_id=request_id,
            champion_slot_id=request.target_champion_slot_id,
            input_hash=request.request_hash,
        )
        try:
            saga = await self._apply_promotion(
                approved_request,
                approved_by=str(approved_by),
                now=now,
            )
        except Exception:
            failed_request = approved_request.model_copy(
                update={"status": "FAILED"}
            )
            await self.db["ag_exp_promotion_requests"].replace_one(
                {"promotion_request_id": request_id},
                experiment_document(failed_request),
            )
            raise
        return approval, saga

    async def _write_saga(
        self, saga: PromotionSaga
    ) -> PromotionSaga:
        await self.db["ag_exp_promotion_sagas"].replace_one(
            {"promotion_saga_id": saga.promotion_saga_id},
            experiment_document(saga),
            upsert=True,
        )
        return saga

    async def _apply_promotion(
        self,
        request: PromotionRequest,
        *,
        approved_by: str,
        now: datetime,
    ) -> PromotionSaga:
        current_raw = await self.repository.get(
            "champion_assignments",
            {"champion_slot_id": request.target_champion_slot_id},
        )
        current = ChampionAssignment.model_validate(current_raw)
        saga_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:promotion-saga:{request.promotion_request_id}",
            )
        )
        lock_key = f"promotion:{request.target_champion_slot_id}"
        saga = PromotionSaga(
            promotion_saga_id=saga_id,
            operation="PROMOTION",
            promotion_request_id=request.promotion_request_id,
            champion_slot_id=request.target_champion_slot_id,
            status="PREPARED",
            from_version_ref=current.current_version_ref,
            to_version_ref=request.proposed_champion_version_ref,
            expected_assignment_hash=current.assignment_hash,
            effective_from_trade_date=request.effective_from_trade_date,
            lock_key=lock_key,
            created_by=approved_by,
            created_at=now,
            updated_at=now,
        )
        await self._write_saga(saga)
        await self.audit.record(
            "PROMOTION_SAGA_STARTED",
            "recoverable standalone-Mongo promotion saga started",
            experiment_id=request.experiment_id,
            promotion_request_id=request.promotion_request_id,
            promotion_saga_id=saga_id,
            champion_slot_id=request.target_champion_slot_id,
        )
        old_assignment = current
        try:
            if await self.db["ag_exp_locks"].find_one({"_id": lock_key}):
                raise ExperimentIntegrityConflict("Champion slot is locked")
            await self.db["ag_exp_locks"].insert_one(
                {
                    "_id": lock_key,
                    "lock_type": "CHAMPION_PROMOTION",
                    "promotion_saga_id": saga_id,
                    "created_at": now,
                }
            )
            saga = saga.model_copy(
                update={"status": "LOCK_ACQUIRED", "updated_at": datetime.utcnow()}
            )
            await self._write_saga(saga)
            latest_raw = await self.repository.get(
                "champion_assignments",
                {"champion_slot_id": request.target_champion_slot_id},
            )
            latest = ChampionAssignment.model_validate(latest_raw)
            if (
                latest.assignment_hash != saga.expected_assignment_hash
                or latest.current_version_ref != saga.from_version_ref
            ):
                raise ExperimentIntegrityConflict(
                    "current Champion changed during promotion"
                )
            saga = saga.model_copy(
                update={
                    "status": "CURRENT_CHAMPION_VERIFIED",
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._write_saga(saga)
            history = ChampionAssignmentHistory(
                history_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        "alphaguard:champion-history:"
                        f"{latest.champion_slot_id}:{latest.assignment_version}:"
                        f"{latest.assignment_hash}",
                    )
                ),
                champion_slot_id=latest.champion_slot_id,
                assignment=latest,
                committed_saga_id=latest.promotion_saga_id,
                recorded_at=datetime.utcnow(),
            )
            await self.repository.insert_once(
                "champion_history",
                history,
                identity={"history_id": history.history_id},
            )
            payload = {
                "champion_slot_id": latest.champion_slot_id,
                "component_type": latest.component_type,
                "component_key": latest.component_key,
                "market": latest.market,
                "current_version_ref": saga.to_version_ref,
                "previous_version_ref": latest.current_version_ref,
                "source_experiment_id": request.experiment_id,
                "source_promotion_request_id": request.promotion_request_id,
                "effective_from_trade_date": request.effective_from_trade_date,
                "assignment_version": latest.assignment_version + 1,
                "status": "ACTIVE",
                "promotion_saga_id": saga_id,
                "updated_by": approved_by,
                "updated_at": datetime.utcnow(),
            }
            payload["assignment_hash"] = assignment_hash(payload)
            new_assignment = ChampionAssignment.model_validate(payload)
            result = await self.db["ag_exp_champion_assignments"].replace_one(
                {
                    "champion_slot_id": latest.champion_slot_id,
                    "assignment_hash": latest.assignment_hash,
                },
                experiment_document(new_assignment),
            )
            if result.matched_count != 1:
                raise ExperimentIntegrityConflict(
                    "Champion pointer CAS write failed"
                )
            saga = saga.model_copy(
                update={
                    "status": "ASSIGNMENT_WRITTEN",
                    "written_assignment_hash": new_assignment.assignment_hash,
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._write_saga(saga)
            pending = await self.resolver.verify_pending_assignment(
                champion_slot_id=new_assignment.champion_slot_id,
                saga_id=saga_id,
                as_of_trade_date=request.effective_from_trade_date,
            )
            if pending.version_ref != saga.to_version_ref:
                raise ExperimentIntegrityConflict(
                    "pending ChampionResolver verification failed"
                )
            saga = saga.model_copy(
                update={
                    "status": "RESOLVER_VERIFIED",
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._write_saga(saga)
            saga = saga.model_copy(
                update={
                    "status": "COMMITTED",
                    "updated_at": datetime.utcnow(),
                    "committed_at": datetime.utcnow(),
                }
            )
            await self._write_saga(saga)
            resolved = await self.resolver.resolve_champion(
                component_type=new_assignment.component_type,
                component_key=new_assignment.component_key,
                market=new_assignment.market,
                as_of_trade_date=request.effective_from_trade_date,
            )
            if resolved.version_ref != saga.to_version_ref:
                raise ExperimentIntegrityConflict(
                    "committed ChampionResolver verification failed"
                )
            new_history = ChampionAssignmentHistory(
                history_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        "alphaguard:champion-history:"
                        f"{new_assignment.champion_slot_id}:"
                        f"{new_assignment.assignment_version}:"
                        f"{new_assignment.assignment_hash}",
                    )
                ),
                champion_slot_id=new_assignment.champion_slot_id,
                assignment=new_assignment,
                committed_saga_id=saga_id,
                recorded_at=datetime.utcnow(),
            )
            await self.repository.insert_once(
                "champion_history",
                new_history,
                identity={"history_id": new_history.history_id},
            )
            applied = request.model_copy(update={"status": "APPLIED"})
            await self.db["ag_exp_promotion_requests"].replace_one(
                {"promotion_request_id": request.promotion_request_id},
                experiment_document(applied),
            )
            await self.registry.transition(
                request.experiment_id,
                "CHAMPION",
                human_approval_applied=True,
                reason="human-approved PromotionSaga COMMITTED",
            )
            await self.audit.record(
                "PROMOTION_SAGA_COMMITTED",
                "new Champion pointer is committed for future effective tasks",
                experiment_id=request.experiment_id,
                promotion_request_id=request.promotion_request_id,
                promotion_saga_id=saga_id,
                champion_slot_id=request.target_champion_slot_id,
                baseline_version_ref=saga.from_version_ref,
                challenger_version_ref=saga.to_version_ref,
                current_champion_version_ref=saga.to_version_ref,
                result_hash=new_assignment.assignment_hash,
            )
            await self.audit.record(
                "CHAMPION_CHANGED",
                "old version retained; only future effective tasks resolve new Champion",
                experiment_id=request.experiment_id,
                promotion_request_id=request.promotion_request_id,
                promotion_saga_id=saga_id,
                champion_slot_id=request.target_champion_slot_id,
                current_champion_version_ref=saga.to_version_ref,
            )
            return saga
        except Exception as exc:
            current_after = await self.repository.get(
                "champion_assignments",
                {"champion_slot_id": request.target_champion_slot_id},
            )
            if current_after and current_after.get("promotion_saga_id") == saga_id:
                await self.db["ag_exp_champion_assignments"].replace_one(
                    {"champion_slot_id": old_assignment.champion_slot_id},
                    experiment_document(old_assignment),
                )
                terminal = "ROLLED_BACK"
            else:
                terminal = "FAILED"
            saga = saga.model_copy(
                update={
                    "status": terminal,
                    "last_error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._write_saga(saga)
            await self.audit.record(
                (
                    "PROMOTION_SAGA_ROLLED_BACK"
                    if terminal == "ROLLED_BACK"
                    else "PROMOTION_SAGA_FAILED"
                ),
                saga.last_error or terminal,
                experiment_id=request.experiment_id,
                promotion_request_id=request.promotion_request_id,
                promotion_saga_id=saga_id,
                champion_slot_id=request.target_champion_slot_id,
            )
            raise
        finally:
            await self.db["ag_exp_locks"].delete_one({"_id": lock_key})

    async def recover_incomplete_sagas(self) -> dict[str, int]:
        documents = await self.repository.list(
            "promotion_sagas",
            {
                "status": {
                    "$nin": ["COMMITTED", "ROLLED_BACK", "FAILED"]
                }
            },
        )
        counts = {"committed": 0, "rolled_back": 0, "failed": 0}
        for item in documents:
            saga = PromotionSaga.model_validate(item)
            if saga.operation != "PROMOTION" or not saga.promotion_request_id:
                counts["failed"] += 1
                continue
            request_raw = await self.repository.get(
                "promotion_requests",
                {"promotion_request_id": saga.promotion_request_id},
            )
            if request_raw is None or request_raw.get("status") not in {
                "APPROVED",
                "APPLIED",
            }:
                counts["failed"] += 1
                continue
            request = PromotionRequest.model_validate(request_raw)
            current = await self.repository.get(
                "champion_assignments",
                {"champion_slot_id": saga.champion_slot_id},
            )
            if (
                current
                and current.get("promotion_saga_id")
                == saga.promotion_saga_id
                and current.get("assignment_hash")
                == saga.written_assignment_hash
            ):
                try:
                    assignment = ChampionAssignment.model_validate(current)
                    pending = await self.resolver.verify_pending_assignment(
                        champion_slot_id=assignment.champion_slot_id,
                        saga_id=saga.promotion_saga_id,
                        as_of_trade_date=saga.effective_from_trade_date,
                    )
                    if pending.version_ref != saga.to_version_ref:
                        raise ExperimentIntegrityConflict(
                            "recovered pending resolver verification failed"
                        )
                    verified = saga.model_copy(
                        update={
                            "status": "RESOLVER_VERIFIED",
                            "updated_at": datetime.utcnow(),
                        }
                    )
                    await self._write_saga(verified)
                    committed = verified.model_copy(
                        update={
                            "status": "COMMITTED",
                            "committed_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow(),
                        }
                    )
                    await self._write_saga(committed)
                    resolved = await self.resolver.resolve_champion(
                        component_type=assignment.component_type,
                        component_key=assignment.component_key,
                        market=assignment.market,
                        as_of_trade_date=saga.effective_from_trade_date,
                    )
                    if resolved.version_ref != saga.to_version_ref:
                        raise ExperimentIntegrityConflict(
                            "recovered committed resolver verification failed"
                        )
                    history = ChampionAssignmentHistory(
                        history_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                "alphaguard:champion-history:"
                                f"{assignment.champion_slot_id}:"
                                f"{assignment.assignment_version}:"
                                f"{assignment.assignment_hash}",
                            )
                        ),
                        champion_slot_id=assignment.champion_slot_id,
                        assignment=assignment,
                        committed_saga_id=saga.promotion_saga_id,
                        recorded_at=datetime.utcnow(),
                    )
                    await self.repository.insert_once(
                        "champion_history",
                        history,
                        identity={"history_id": history.history_id},
                    )
                    applied = request.model_copy(update={"status": "APPLIED"})
                    await self.db["ag_exp_promotion_requests"].replace_one(
                        {
                            "promotion_request_id": request.promotion_request_id
                        },
                        experiment_document(applied),
                    )
                    definition = await self.registry.get(
                        request.experiment_id
                    )
                    if definition.status == "CHALLENGER":
                        await self.registry.transition(
                            request.experiment_id,
                            "CHAMPION",
                            human_approval_applied=True,
                            reason=(
                                "recovered human-approved PromotionSaga "
                                "COMMITTED"
                            ),
                        )
                    await self.audit.record(
                        "PROMOTION_SAGA_COMMITTED",
                        "incomplete human-approved saga recovered and committed",
                        experiment_id=request.experiment_id,
                        promotion_request_id=request.promotion_request_id,
                        promotion_saga_id=saga.promotion_saga_id,
                        champion_slot_id=saga.champion_slot_id,
                        baseline_version_ref=saga.from_version_ref,
                        challenger_version_ref=saga.to_version_ref,
                        current_champion_version_ref=saga.to_version_ref,
                        result_hash=assignment.assignment_hash,
                    )
                    counts["committed"] += 1
                except Exception as exc:
                    await self._rollback_incomplete_saga(
                        saga, request, error=exc
                    )
                    counts["rolled_back"] += 1
            else:
                try:
                    await self._rollback_incomplete_saga(
                        saga,
                        request,
                        error=ExperimentIntegrityConflict(
                            "incomplete saga has no verifiable written assignment"
                        ),
                    )
                    counts["rolled_back"] += 1
                except Exception:
                    failed = saga.model_copy(
                        update={
                            "status": "FAILED",
                            "last_error": (
                                "no recoverable Champion history for "
                                "incomplete saga"
                            ),
                            "updated_at": datetime.utcnow(),
                        }
                    )
                    await self._write_saga(failed)
                    counts["failed"] += 1
            await self.db["ag_exp_locks"].delete_one(
                {"_id": saga.lock_key}
            )
        return counts

    async def _rollback_incomplete_saga(
        self,
        saga: PromotionSaga,
        request: PromotionRequest,
        *,
        error: Exception,
    ) -> None:
        history = await self.repository.list(
            "champion_history",
            {"champion_slot_id": saga.champion_slot_id},
            sort=("recorded_at", -1),
            limit=20,
        )
        prior = next(
            (
                ChampionAssignmentHistory.model_validate(item).assignment
                for item in history
                if ChampionAssignmentHistory.model_validate(
                    item
                ).assignment.assignment_hash
                == saga.expected_assignment_hash
            ),
            None,
        )
        if prior is None:
            raise ExperimentIntegrityConflict(
                "no matching prior ChampionAssignment history"
            )
        await self.db["ag_exp_champion_assignments"].replace_one(
            {"champion_slot_id": saga.champion_slot_id},
            experiment_document(prior),
            upsert=True,
        )
        rolled = saga.model_copy(
            update={
                "status": "ROLLED_BACK",
                "last_error": f"{type(error).__name__}: {str(error)[:500]}",
                "updated_at": datetime.utcnow(),
            }
        )
        await self._write_saga(rolled)
        failed_request = request.model_copy(update={"status": "FAILED"})
        await self.db["ag_exp_promotion_requests"].replace_one(
            {"promotion_request_id": request.promotion_request_id},
            experiment_document(failed_request),
        )
        await self.audit.record(
            "PROMOTION_SAGA_ROLLED_BACK",
            rolled.last_error or "recovery rollback",
            experiment_id=request.experiment_id,
            promotion_request_id=request.promotion_request_id,
            promotion_saga_id=saga.promotion_saga_id,
            champion_slot_id=saga.champion_slot_id,
            current_champion_version_ref=prior.current_version_ref,
        )
