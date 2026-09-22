"""
工作流成长服务

负责在统一任务完成后提取候选记忆与成长建议，并提供审核查询能力。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_mongo_db
from app.models.agent_growth import (
    AgentGrowthMemoryItem,
    AgentGrowthSuggestion,
    GrowthEvidenceRef,
    GrowthMemoryScope,
    GrowthMemoryStatus,
    GrowthReviewLevel,
    GrowthSuggestionStatus,
    GrowthSuggestionType,
    TaskGrowthContext,
)
from app.models.analysis import AnalysisTaskType, UnifiedAnalysisTask
from app.utils.timezone import now_tz
from core.agents.config import GrowthMemoryScope as AgentGrowthMemoryScope
from core.agents.config import GrowthReviewLevel as AgentGrowthReviewLevel
from core.agents.config import GrowthSourceType as AgentGrowthSourceType
from core.agents.registry import get_registry
from core.memory.models import MemoryScope

logger = logging.getLogger(__name__)


GROWTH_FIELD_TITLES: Dict[str, str] = {
    "index_report": "大盘与宏观跟踪项",
    "sector_report": "板块轮动与行业跟踪项",
    "market_report": "技术面检查项",
    "fundamentals_report": "基本面检查项",
    "news_report": "事件与新闻证据",
    "sentiment_report": "情绪与舆情证据",
    "bull_report": "积极证据观点",
    "bear_report": "谨慎证据观点",
    "neutral_opinion": "基准情景研究观察",
    "risky_opinion": "高弹性情景研究观察",
    "safe_opinion": "防御情景研究观察",
    "investment_plan": "综合研究结论",
    "investment_debate_state": "多情景研究状态",
    "risk_assessment": "风险审阅",
    "risk_debate_state": "风险多情景研究状态",
    "final_trade_decision": "综合研究结论",
    "trader_investment_plan": "研究简报",
    "timing_analysis": "时机分析",
    "position_analysis": "仓位分析",
    "emotion_analysis": "情绪分析",
    "attribution_analysis": "归因分析",
    "review_summary": "复盘总结",
    "technical_analysis": "持仓技术检查项",
    "fundamental_analysis": "持仓基本面检查项",
    "risk_analysis": "持仓风险边界",
    "action_advice": "研究观察模板",
}


class WorkflowGrowthService:
    """工作流成长服务。"""

    def __init__(self):
        self.db = get_mongo_db()
        self.memory_collection = self.db.agent_memory_items
        self.suggestion_collection = self.db.agent_growth_suggestions
        self._growth_field_profiles = self._load_growth_field_profiles()

    async def process_completed_task(
        self,
        task: UnifiedAnalysisTask,
        raw_result: Dict[str, Any],
        formatted_result: Dict[str, Any],
        analysis_id: Optional[str] = None,
    ) -> TaskGrowthContext:
        """从已完成任务中提取成长产物。"""
        existing = await self._get_task_growth_context(str(task.user_id), task.task_id)
        if existing and (existing.memory_items_count > 0 or existing.suggestions_count > 0):
            return existing

        memory_docs = self._build_memory_candidates(task, raw_result, formatted_result, analysis_id)
        suggestion_docs = self._build_suggestion_candidates(task, raw_result, formatted_result, analysis_id)

        memory_items = [AgentGrowthMemoryItem(**doc) for doc in memory_docs]
        suggestion_items = [AgentGrowthSuggestion(**doc) for doc in suggestion_docs]

        memory_ids = [item.memory_id for item in memory_items]
        suggestion_ids = [item.suggestion_id for item in suggestion_items]

        if memory_items:
            await self.memory_collection.insert_many(
                [item.model_dump(by_alias=True, mode="python") for item in memory_items],
                ordered=False,
            )

        if suggestion_items:
            await self.suggestion_collection.insert_many(
                [item.model_dump(by_alias=True, mode="python") for item in suggestion_items],
                ordered=False,
            )

        return TaskGrowthContext(
            memory_items_count=len(memory_ids),
            suggestions_count=len(suggestion_ids),
            memory_item_ids=memory_ids,
            suggestion_ids=suggestion_ids,
            extracted_at=now_tz(),
            source_id=task.task_id,
        )

    async def list_memory_items(
        self,
        user_id: str,
        status: Optional[GrowthMemoryStatus] = None,
        scope: Optional[GrowthMemoryScope] = None,
        task_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status.value if hasattr(status, "value") else str(status)
        if scope:
            query["scope"] = scope.value if hasattr(scope, "value") else str(scope)
        if task_id:
            query["source_id"] = task_id

        docs = await self.memory_collection.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        return [self._serialize_doc(doc) for doc in docs]

    async def list_suggestions(
        self,
        user_id: str,
        status: Optional[GrowthSuggestionStatus] = None,
        task_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status.value if hasattr(status, "value") else str(status)
        if task_id:
            query["source_id"] = task_id

        docs = await self.suggestion_collection.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        return [self._serialize_doc(doc) for doc in docs]

    async def approve_memory_item(self, user_id: str, memory_id: str) -> bool:
        now = now_tz()
        result = await self.memory_collection.update_one(
            {"user_id": user_id, "memory_id": memory_id},
            {
                "$set": {
                    "status": GrowthMemoryStatus.APPROVED.value,
                    "confirmed_by": user_id,
                    "confirmed_at": now,
                    "updated_at": now,
                }
            },
        )
        if result.modified_count > 0:
            approved_doc = await self.memory_collection.find_one({"user_id": user_id, "memory_id": memory_id})
            if approved_doc:
                await self._sync_approved_memory_to_mem0(approved_doc)
        return result.modified_count > 0

    async def reject_memory_item(self, user_id: str, memory_id: str) -> bool:
        now = now_tz()
        result = await self.memory_collection.update_one(
            {"user_id": user_id, "memory_id": memory_id},
            {
                "$set": {
                    "status": GrowthMemoryStatus.REJECTED.value,
                    "rejected_by": user_id,
                    "rejected_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    async def accept_suggestion(self, user_id: str, suggestion_id: str) -> Optional[Dict[str, Any]]:
        now = now_tz()
        suggestion_doc = await self.suggestion_collection.find_one({"user_id": user_id, "suggestion_id": suggestion_id})
        if not suggestion_doc:
            return None

        activation_result = await self._execute_suggested_action(user_id, suggestion_doc)
        result = await self.suggestion_collection.update_one(
            {"user_id": user_id, "suggestion_id": suggestion_id},
            {
                "$set": {
                    "status": GrowthSuggestionStatus.ACCEPTED.value,
                    "accepted_by": user_id,
                    "accepted_at": now,
                    "activation_result": activation_result,
                    "updated_at": now,
                }
            },
        )
        if result.modified_count <= 0:
            return None

        updated_doc = await self.suggestion_collection.find_one({"user_id": user_id, "suggestion_id": suggestion_id})
        if not updated_doc:
            return {"suggestion_id": suggestion_id, "activation_result": activation_result}
        return self._serialize_doc(updated_doc)

    async def dismiss_suggestion(self, user_id: str, suggestion_id: str) -> bool:
        now = now_tz()
        result = await self.suggestion_collection.update_one(
            {"user_id": user_id, "suggestion_id": suggestion_id},
            {
                "$set": {
                    "status": GrowthSuggestionStatus.DISMISSED.value,
                    "dismissed_by": user_id,
                    "dismissed_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    async def get_task_context(self, user_id: str, task_id: str) -> Dict[str, Any]:
        memories = await self.list_memory_items(user_id=user_id, task_id=task_id, limit=100)
        suggestions = await self.list_suggestions(user_id=user_id, task_id=task_id, limit=100)
        return {
            "task_id": task_id,
            "memory_items": memories,
            "suggestions": suggestions,
            "summary": {
                "memory_items_count": len(memories),
                "suggestions_count": len(suggestions),
            },
        }

    async def build_recall_context(
        self,
        user_id: str,
        ticker: Optional[str] = None,
        workflow_id: Optional[str] = None,
        max_items: int = 10,
        max_chars: int = 3000,
    ) -> str:
        """
        为即将执行的工作流构建已批准记忆的召回上下文。

        按优先级查询: object_tracking（与标的相关）> pattern >
        research_asset，拼接为结构化文本注入工作流输入。

        Returns:
            可直接注入提示词的 Markdown 文本，无记忆时返回空字符串
        """
        query: Dict[str, Any] = {
            "user_id": user_id,
            "status": GrowthMemoryStatus.APPROVED.value,
        }

        recall_items: List[Dict[str, Any]] = []

        # 优先级 1: 与当前标的相关的 object_tracking 记忆
        if ticker:
            obj_query = {**query, "object_key": ticker}
            docs = await (
                self.memory_collection
                .find(obj_query)
                .sort("updated_at", -1)
                .limit(max_items)
                .to_list(length=max_items)
            )
            recall_items.extend(docs)

        remaining = max_items - len(recall_items)

        # 优先级 2: pattern 记忆
        if remaining > 0 and workflow_id:
            wf_query = {
                **query,
                "scope": GrowthMemoryScope.PATTERN.value,
                "workflow_id": workflow_id,
            }
            seen_ids = {str(d.get("_id")) for d in recall_items}
            docs = await (
                self.memory_collection
                .find(wf_query)
                .sort("updated_at", -1)
                .limit(remaining)
                .to_list(length=remaining)
            )
            for d in docs:
                if str(d.get("_id")) not in seen_ids:
                    recall_items.append(d)

        remaining = max_items - len(recall_items)

        # 优先级 3: research_asset 记忆
        if remaining > 0:
            ra_query = {
                **query,
                "scope": GrowthMemoryScope.RESEARCH_ASSET.value,
            }
            seen_ids = {str(d.get("_id")) for d in recall_items}
            docs = await (
                self.memory_collection
                .find(ra_query)
                .sort("updated_at", -1)
                .limit(remaining)
                .to_list(length=remaining)
            )
            for d in docs:
                if str(d.get("_id")) not in seen_ids:
                    recall_items.append(d)

        if not recall_items:
            return ""

        # 拼接为结构化文本
        lines = ["## 历史研究记忆（已审核批准）\n"]
        total_chars = 0
        for item in recall_items:
            title = item.get("title", "")
            summary = item.get("summary") or item.get("content", "")
            scope = item.get("scope", "")
            obj_key = item.get("object_key", "")

            if len(summary) > 500:
                summary = summary[:500] + "…"

            entry = f"- **{title}**"
            if obj_key:
                entry += f" [{obj_key}]"
            if scope:
                entry += f" ({scope})"
            entry += f"\n  {summary}\n"

            if total_chars + len(entry) > max_chars:
                break
            lines.append(entry)
            total_chars += len(entry)

        return "\n".join(lines)

    async def _get_task_growth_context(self, user_id: str, task_id: str) -> TaskGrowthContext:
        memories = await self.memory_collection.count_documents({"user_id": user_id, "source_id": task_id})
        suggestions = await self.suggestion_collection.count_documents({"user_id": user_id, "source_id": task_id})
        return TaskGrowthContext(
            memory_items_count=memories,
            suggestions_count=suggestions,
            memory_item_ids=[],
            suggestion_ids=[],
            extracted_at=now_tz(),
            source_id=task_id,
        )

    def _build_memory_candidates(
        self,
        task: UnifiedAnalysisTask,
        raw_result: Dict[str, Any],
        formatted_result: Dict[str, Any],
        analysis_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        object_type, object_key = self._resolve_object_binding(task)
        evidence_refs = self._build_evidence_refs(task, analysis_id)
        metadata_artifacts = self._extract_metadata_growth_artifacts(raw_result, formatted_result)
        candidates = self._build_metadata_memory_candidates(
            task=task,
            artifacts=metadata_artifacts,
            analysis_id=analysis_id,
            object_type=object_type,
            object_key=object_key,
            evidence_refs=evidence_refs,
        )

        summary_candidate = self._build_summary_memory_candidate(
            task=task,
            formatted_result=formatted_result,
            metadata_artifacts=metadata_artifacts,
            analysis_id=analysis_id,
            object_type=object_type,
            object_key=object_key,
            evidence_refs=evidence_refs,
        )
        if summary_candidate:
            candidates.append(summary_candidate)

        pattern_candidate = self._build_pattern_memory_candidate(
            task=task,
            raw_result=raw_result,
            metadata_artifacts=metadata_artifacts,
            object_type=object_type,
            object_key=object_key,
            evidence_refs=evidence_refs,
        )
        if pattern_candidate:
            candidates.append(pattern_candidate)

        return candidates

    def _build_metadata_memory_candidates(
        self,
        task: UnifiedAnalysisTask,
        artifacts: List[Dict[str, Any]],
        analysis_id: Optional[str],
        object_type: Optional[str],
        object_key: Optional[str],
        evidence_refs: List[GrowthEvidenceRef],
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen_fields: set[str] = set()

        for artifact in artifacts:
            field_name = artifact["field"]
            if field_name in seen_fields:
                continue

            seen_fields.add(field_name)
            content = self._extract_text(artifact["content"])
            if not content:
                continue

            candidates.append(
                self._make_memory_doc(
                    task=task,
                    object_type=object_type,
                    object_key=object_key,
                    title=f"{self._object_label(task)}{artifact['title']}",
                    summary=self._summarize_text(content),
                    content=content,
                    scope=artifact["scope"],
                    review_level=artifact["review_level"],
                    confidence=artifact["confidence"],
                    evidence_refs=evidence_refs,
                    structured_payload={
                        "source_field": field_name,
                        "analysis_id": analysis_id,
                        "growth_source_type": artifact["growth_source_type"],
                        "agent_name": artifact.get("agent_name"),
                    },
                )
            )

        return candidates

    def _build_summary_memory_candidate(
        self,
        task: UnifiedAnalysisTask,
        formatted_result: Dict[str, Any],
        metadata_artifacts: List[Dict[str, Any]],
        analysis_id: Optional[str],
        object_type: Optional[str],
        object_key: Optional[str],
        evidence_refs: List[GrowthEvidenceRef],
    ) -> Optional[Dict[str, Any]]:
        summary = self._extract_text(formatted_result.get("summary")) if isinstance(formatted_result, dict) else ""
        key_points = formatted_result.get("key_points", []) if isinstance(formatted_result, dict) else []
        if not summary and not key_points:
            return None

        has_research_asset = any(
            artifact["scope"] == GrowthMemoryScope.RESEARCH_ASSET for artifact in metadata_artifacts
        )
        has_object_tracking = any(
            artifact["scope"] == GrowthMemoryScope.OBJECT_TRACKING for artifact in metadata_artifacts
        )

        if object_type != "stock":
            return None

        if not (has_research_asset or (has_object_tracking and key_points)):
            return None

        title = "研究摘要候选"
        content_parts = []
        if summary:
            content_parts.append(summary)
        if key_points:
            content_parts.append("关键要点：\n- " + "\n- ".join(key_points[:5]))

        return self._make_memory_doc(
            task=task,
            object_type=object_type,
            object_key=object_key,
            title=f"{self._object_label(task)}{title}",
            summary=self._summarize_text(summary or "\n".join(key_points[:3])),
            content="\n\n".join(content_parts),
            scope=GrowthMemoryScope.RESEARCH_ASSET,
            review_level=GrowthReviewLevel.MANUAL_REQUIRED,
            confidence=0.78,
            evidence_refs=evidence_refs,
            structured_payload={"key_points": key_points[:5], "analysis_id": analysis_id},
        )

    def _build_pattern_memory_candidate(
        self,
        task: UnifiedAnalysisTask,
        raw_result: Dict[str, Any],
        metadata_artifacts: List[Dict[str, Any]],
        object_type: Optional[str],
        object_key: Optional[str],
        evidence_refs: List[GrowthEvidenceRef],
    ) -> Optional[Dict[str, Any]]:
        weaknesses = self._list_value(raw_result, "weaknesses")
        suggestions = self._list_value(raw_result, "suggestions")
        strengths = self._list_value(raw_result, "strengths")
        review_summary = self._extract_text(self._get_value(raw_result, "summary"))

        has_review_artifact = any(
            artifact.get("growth_source_type") == AgentGrowthSourceType.REVIEW_REPORT.value
            or artifact.get("field") == "review_summary"
            for artifact in metadata_artifacts
        )
        if not has_review_artifact and not (weaknesses or suggestions):
            return None
        if not (weaknesses or suggestions or review_summary):
            return None

        title = "复盘偏差模式" if object_type == "trade_review" else "经验模式候选"
        content_parts = []
        if review_summary:
            content_parts.append(review_summary)
        if strengths:
            content_parts.append("保留做法：\n- " + "\n- ".join(strengths[:5]))
        if weaknesses:
            content_parts.append("高频偏差：\n- " + "\n- ".join(weaknesses[:5]))
        if suggestions:
            content_parts.append("改进建议：\n- " + "\n- ".join(suggestions[:5]))

        return self._make_memory_doc(
            task=task,
            object_type=object_type,
            object_key=object_key,
            title=f"{self._object_label(task)}{title}",
            summary=self._summarize_text(review_summary or "；".join(weaknesses[:2]) or "；".join(suggestions[:2])),
            content="\n\n".join(content_parts),
            scope=GrowthMemoryScope.PATTERN,
            review_level=GrowthReviewLevel.MANUAL_REQUIRED,
            confidence=0.82,
            evidence_refs=evidence_refs,
            structured_payload={"weaknesses": weaknesses[:5], "suggestions": suggestions[:5], "strengths": strengths[:5]},
        )

    def _extract_metadata_growth_artifacts(
        self,
        raw_result: Dict[str, Any],
        formatted_result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        reports = formatted_result.get("reports", {}) if isinstance(formatted_result, dict) else {}
        candidate_sources: List[Dict[str, Any]] = []
        if isinstance(raw_result, dict):
            candidate_sources.append(raw_result)
        if isinstance(reports, dict):
            candidate_sources.append(reports)
        if isinstance(formatted_result, dict):
            candidate_sources.append(formatted_result)

        artifacts: List[Dict[str, Any]] = []
        for field_name, profile in self._growth_field_profiles.items():
            value = None
            for source in candidate_sources:
                if field_name in source and source.get(field_name) not in (None, "", [], {}):
                    value = source.get(field_name)
                    break

            if value in (None, "", [], {}):
                continue

            artifacts.append(
                {
                    "field": field_name,
                    "title": profile["title"],
                    "content": value,
                    "growth_role": profile.get("growth_role"),
                    "scope": profile["memory_scope_hint"],
                    "review_level": profile["review_level"],
                    "growth_source_type": profile["growth_source_type"],
                    "agent_name": profile.get("agent_name"),
                    "confidence": self._estimate_artifact_confidence(
                        profile["review_level"],
                        profile["memory_scope_hint"],
                        profile["growth_source_type"],
                    ),
                }
            )

        return artifacts

    def _load_growth_field_profiles(self) -> Dict[str, Dict[str, Any]]:
        try:
            from core.agents import adapters as _agent_adapters  # noqa: F401

            registry = get_registry()
            profiles: Dict[str, Dict[str, Any]] = {}

            for metadata in registry.list_all():
                growth_role = self._coerce_growth_role(getattr(metadata, "growth_role", None))
                if growth_role == "none":
                    continue

                output_fields = list(getattr(metadata, "growth_outputs", None) or [])
                if not output_fields and getattr(metadata, "output_field", None):
                    output_fields = [metadata.output_field]

                if not output_fields:
                    continue

                review_level = self._coerce_review_level(getattr(metadata, "review_level", None))
                memory_scope = self._coerce_memory_scope(getattr(metadata, "memory_scope_hint", None))
                source_type = self._coerce_source_type(getattr(metadata, "growth_source_type", None))

                for field_name in output_fields:
                    profiles.setdefault(
                        field_name,
                        {
                            "title": GROWTH_FIELD_TITLES.get(field_name) or f"{metadata.name}输出",
                            "growth_role": growth_role,
                            "review_level": review_level,
                            "memory_scope_hint": memory_scope,
                            "growth_source_type": source_type,
                            "agent_name": metadata.name,
                        },
                    )

            return profiles
        except Exception as exc:
            logger.warning(f"⚠️ 加载成长字段配置失败，将退回现有硬编码逻辑: {exc}")
            return {}

    def _coerce_memory_scope(self, value: Any) -> GrowthMemoryScope:
        raw_value = value.value if hasattr(value, "value") else value
        if raw_value == AgentGrowthMemoryScope.OBJECT_TRACKING.value:
            return GrowthMemoryScope.OBJECT_TRACKING
        if raw_value == AgentGrowthMemoryScope.PATTERN.value:
            return GrowthMemoryScope.PATTERN
        if raw_value == AgentGrowthMemoryScope.RESEARCH_ASSET.value:
            return GrowthMemoryScope.RESEARCH_ASSET
        return GrowthMemoryScope.PATTERN

    def _coerce_review_level(self, value: Any) -> GrowthReviewLevel:
        raw_value = value.value if hasattr(value, "value") else value
        if raw_value == AgentGrowthReviewLevel.AUTO_PENDING.value:
            return GrowthReviewLevel.AUTO_PENDING
        return GrowthReviewLevel.MANUAL_REQUIRED

    def _coerce_source_type(self, value: Any) -> str:
        raw_value = value.value if hasattr(value, "value") else value
        if raw_value in {
            AgentGrowthSourceType.ANALYSIS_REPORT.value,
            AgentGrowthSourceType.REVIEW_REPORT.value,
            AgentGrowthSourceType.MANAGER_DECISION.value,
        }:
            return raw_value
        return AgentGrowthSourceType.NONE.value

    def _coerce_growth_role(self, value: Any) -> str:
        raw_value = value.value if hasattr(value, "value") else value
        normalized = str(raw_value or "none")
        if normalized in {"extractor", "reviewer", "optimizer", "none"}:
            return normalized
        return "none"

    def _estimate_artifact_confidence(
        self,
        review_level: GrowthReviewLevel,
        memory_scope: GrowthMemoryScope,
        source_type: str,
    ) -> float:
        confidence = 0.62 if review_level == GrowthReviewLevel.MANUAL_REQUIRED else 0.74
        if memory_scope == GrowthMemoryScope.RESEARCH_ASSET:
            confidence += 0.1
        elif memory_scope == GrowthMemoryScope.OBJECT_TRACKING:
            confidence += 0.04

        if source_type == AgentGrowthSourceType.MANAGER_DECISION.value:
            confidence += 0.08
        elif source_type == AgentGrowthSourceType.REVIEW_REPORT.value:
            confidence += 0.04

        return min(round(confidence, 2), 0.92)

    def _build_suggestion_candidates(
        self,
        task: UnifiedAnalysisTask,
        raw_result: Dict[str, Any],
        formatted_result: Dict[str, Any],
        analysis_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        object_type, object_key = self._resolve_object_binding(task)
        evidence_refs = self._build_evidence_refs(task, analysis_id)
        metadata_artifacts = self._extract_metadata_growth_artifacts(raw_result, formatted_result)
        suggestions = self._build_metadata_suggestion_candidates(
            task=task,
            artifacts=metadata_artifacts,
            object_type=object_type,
            object_key=object_key,
            evidence_refs=evidence_refs,
        )

        if object_type == "stock":
            decision = formatted_result.get("decision", {}) if isinstance(formatted_result, dict) else {}
            key_points = formatted_result.get("key_points", []) if isinstance(formatted_result, dict) else []
            reasoning = self._extract_text(decision.get("reasoning"))
            if (reasoning or key_points) and not self._has_suggestion(
                suggestions,
                suggestion_type=GrowthSuggestionType.WATCH_RULE_SUGGESTION,
                target="object_tracking",
            ):
                payload = {
                    "target": "object_tracking",
                    "mode": "follow_up_focus",
                    "payload": {
                        "symbol": object_key,
                        "focus_points": key_points[:5],
                        "decision_action": decision.get("action"),
                    },
                }
                suggestions.append(
                    self._make_suggestion_doc(
                        task=task,
                        object_type=object_type,
                        object_key=object_key,
                        suggestion_type=GrowthSuggestionType.WATCH_RULE_SUGGESTION,
                        title=f"建议为 {self._object_label(task).strip()}建立后续跟踪项",
                        summary=self._summarize_text(reasoning or "；".join(key_points[:3])),
                        confidence=0.72,
                        source_refs=evidence_refs,
                        suggested_action=payload,
                    )
                )

        weaknesses = self._list_value(raw_result, "weaknesses")
        suggestions_list = self._list_value(raw_result, "suggestions")
        has_review_artifact = any(
            artifact.get("growth_source_type") == AgentGrowthSourceType.REVIEW_REPORT.value
            or artifact.get("field") == "review_summary"
            for artifact in metadata_artifacts
        )
        if (weaknesses or suggestions_list) and has_review_artifact and not self._has_suggestion(
                suggestions,
                suggestion_type=GrowthSuggestionType.WORKFLOW_OPTIMIZATION,
                mode="start_session",
            ) and task.workflow_id:
            suggestions.append(
                self._make_suggestion_doc(
                    task=task,
                    object_type=object_type,
                    object_key=object_key,
                    suggestion_type=GrowthSuggestionType.WORKFLOW_OPTIMIZATION,
                    title="建议为交易复盘流程补充纪律与偏差检查",
                    summary=self._summarize_text("；".join((weaknesses + suggestions_list)[:4])),
                    confidence=0.8,
                    source_refs=evidence_refs,
                    suggested_action={
                        "target": "workflow_generation",
                        "mode": "start_session",
                        "payload": {
                            "workflow_id": task.workflow_id,
                            "description": "根据复盘偏差模式优化复盘流程，补充纪律与执行偏差检查节点",
                        },
                    },
                )
            )

        return suggestions

    def _build_metadata_suggestion_candidates(
        self,
        task: UnifiedAnalysisTask,
        artifacts: List[Dict[str, Any]],
        object_type: Optional[str],
        object_key: Optional[str],
        evidence_refs: List[GrowthEvidenceRef],
    ) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for artifact in artifacts:
            field_name = artifact["field"]
            content = self._extract_text(artifact["content"])
            if not content:
                continue

            metadata_suggestion = self._make_metadata_suggestion_doc(
                task=task,
                object_type=object_type,
                object_key=object_key,
                artifact=artifact,
                evidence_refs=evidence_refs,
            )
            if not metadata_suggestion:
                continue

            key = (
                metadata_suggestion["suggestion_type"],
                str(metadata_suggestion.get("suggested_action", {}).get("mode") or field_name),
            )
            if key in seen_keys:
                continue

            seen_keys.add(key)
            suggestions.append(metadata_suggestion)

        return suggestions

    def _make_metadata_suggestion_doc(
        self,
        task: UnifiedAnalysisTask,
        object_type: Optional[str],
        object_key: Optional[str],
        artifact: Dict[str, Any],
        evidence_refs: List[GrowthEvidenceRef],
    ) -> Optional[Dict[str, Any]]:
        field_name = artifact["field"]
        scope = artifact["scope"]
        growth_role = artifact.get("growth_role")
        source_type = artifact.get("growth_source_type")
        summary = self._summarize_text(self._extract_text(artifact["content"]))
        title = artifact["title"]

        if task.task_type in (AnalysisTaskType.STOCK_ANALYSIS, AnalysisTaskType.ETF_ANALYSIS):
            if scope == GrowthMemoryScope.OBJECT_TRACKING and object_key:
                return self._make_suggestion_doc(
                    task=task,
                    object_type=object_type,
                    object_key=object_key,
                    suggestion_type=GrowthSuggestionType.WATCH_RULE_SUGGESTION,
                    title=f"建议为 {self._object_label(task).strip()}补充{title}跟踪规则",
                    summary=summary,
                    confidence=min(artifact["confidence"] - 0.04, 0.86),
                    source_refs=evidence_refs,
                    suggested_action={
                        "target": "object_tracking",
                        "mode": "follow_up_field",
                        "payload": {
                            "symbol": object_key,
                            "source_field": field_name,
                            "focus_summary": summary,
                            "agent_name": artifact.get("agent_name"),
                        },
                    },
                )

        if task.task_type == AnalysisTaskType.TRADE_REVIEW:
            if growth_role == "optimizer" or source_type == AgentGrowthSourceType.MANAGER_DECISION.value:
                if task.workflow_id:
                    return self._make_suggestion_doc(
                        task=task,
                        object_type=object_type,
                        object_key=object_key,
                        suggestion_type=GrowthSuggestionType.WORKFLOW_OPTIMIZATION,
                        title=f"建议围绕{title}优化当前流程",
                        summary=summary,
                        confidence=min(artifact["confidence"], 0.88),
                        source_refs=evidence_refs,
                        suggested_action={
                            "target": "workflow_generation",
                            "mode": "start_session",
                            "payload": {
                                "workflow_id": task.workflow_id,
                                "description": f"基于{title}沉淀结果优化当前流程，重点吸收字段 {field_name} 的稳定产出。",
                                "source_field": field_name,
                            },
                        },
                    )

        if scope == GrowthMemoryScope.RESEARCH_ASSET:
            return self._make_suggestion_doc(
                task=task,
                object_type=object_type,
                object_key=object_key,
                suggestion_type=GrowthSuggestionType.RESEARCH_ASSET_PROMOTION,
                title=f"建议沉淀{self._object_label(task)}{title}",
                summary=summary,
                confidence=min(artifact["confidence"], 0.9),
                source_refs=evidence_refs,
                suggested_action={
                    "target": "research_asset",
                    "mode": "promote_growth_asset",
                    "payload": {
                        "source_field": field_name,
                        "workflow_id": task.workflow_id,
                        "object_key": object_key,
                        "agent_name": artifact.get("agent_name"),
                    },
                },
            )

        if growth_role == "optimizer" or source_type == AgentGrowthSourceType.MANAGER_DECISION.value:
            if task.workflow_id:
                return self._make_suggestion_doc(
                    task=task,
                    object_type=object_type,
                    object_key=object_key,
                    suggestion_type=GrowthSuggestionType.WORKFLOW_OPTIMIZATION,
                    title=f"建议围绕{title}优化当前流程",
                    summary=summary,
                    confidence=min(artifact["confidence"], 0.88),
                    source_refs=evidence_refs,
                    suggested_action={
                        "target": "workflow_generation",
                        "mode": "start_session",
                        "payload": {
                            "workflow_id": task.workflow_id,
                            "description": f"基于{title}沉淀结果优化当前流程，重点吸收字段 {field_name} 的稳定产出。",
                            "source_field": field_name,
                        },
                    },
                )

        return None

    def _has_suggestion(
        self,
        suggestions: List[Dict[str, Any]],
        suggestion_type: Optional[GrowthSuggestionType] = None,
        mode: Optional[str] = None,
        target: Optional[str] = None,
        source_field: Optional[str] = None,
    ) -> bool:
        expected_type = suggestion_type.value if hasattr(suggestion_type, "value") else suggestion_type

        for suggestion in suggestions:
            if expected_type and suggestion.get("suggestion_type") != expected_type:
                continue

            suggested_action = suggestion.get("suggested_action") or {}
            payload = suggested_action.get("payload") or {}

            if mode and suggested_action.get("mode") != mode:
                continue
            if target and suggested_action.get("target") != target:
                continue
            if source_field and payload.get("source_field") != source_field:
                continue

            return True

        return False

    def _make_memory_doc(
        self,
        task: UnifiedAnalysisTask,
        object_type: Optional[str],
        object_key: Optional[str],
        title: str,
        summary: str,
        content: str,
        scope: GrowthMemoryScope,
        review_level: GrowthReviewLevel,
        confidence: float,
        evidence_refs: List[GrowthEvidenceRef],
        structured_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = now_tz()
        return {
            "memory_id": str(uuid.uuid4()),
            "user_id": str(task.user_id),
            "scope": scope.value,
            "status": GrowthMemoryStatus.PENDING.value,
            "review_level": review_level.value,
            "source_type": "unified_analysis_task",
            "source_id": task.task_id,
            "task_type": str(task.task_type),
            "workflow_id": task.workflow_id,
            "object_type": object_type,
            "object_key": object_key,
            "title": title,
            "summary": summary,
            "content": content,
            "structured_payload": structured_payload,
            "confidence": confidence,
            "evidence_refs": [ref.model_dump() for ref in evidence_refs],
            "created_at": now,
            "updated_at": now,
        }

    def _make_suggestion_doc(
        self,
        task: UnifiedAnalysisTask,
        object_type: Optional[str],
        object_key: Optional[str],
        suggestion_type: GrowthSuggestionType,
        title: str,
        summary: str,
        confidence: float,
        source_refs: List[GrowthEvidenceRef],
        suggested_action: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = now_tz()
        return {
            "suggestion_id": str(uuid.uuid4()),
            "user_id": str(task.user_id),
            "suggestion_type": suggestion_type.value,
            "status": GrowthSuggestionStatus.PENDING.value,
            "source_type": "unified_analysis_task",
            "source_id": task.task_id,
            "task_type": str(task.task_type),
            "workflow_id": task.workflow_id,
            "object_type": object_type,
            "object_key": object_key,
            "title": title,
            "summary": summary,
            "suggested_action": suggested_action,
            "confidence": confidence,
            "source_refs": [ref.model_dump() for ref in source_refs],
            "created_at": now,
            "updated_at": now,
        }

    def _build_evidence_refs(self, task: UnifiedAnalysisTask, analysis_id: Optional[str]) -> List[GrowthEvidenceRef]:
        refs = [GrowthEvidenceRef(type="unified_analysis_task", id=task.task_id, label="统一任务结果")]
        if analysis_id:
            refs.append(GrowthEvidenceRef(type="analysis_report", id=analysis_id, label="分析报告"))
        return refs

    def _resolve_object_binding(self, task: UnifiedAnalysisTask) -> Tuple[Optional[str], Optional[str]]:
        params = task.task_params or {}
        if task.task_type in (AnalysisTaskType.STOCK_ANALYSIS, AnalysisTaskType.ETF_ANALYSIS):
            return "stock", params.get("symbol") or params.get("stock_code")
        if task.task_type == AnalysisTaskType.POSITION_ANALYSIS:
            return "position", params.get("position_id") or params.get("symbol")
        if task.task_type == AnalysisTaskType.TRADE_REVIEW:
            return "trade_review", params.get("review_id") or task.task_id
        return "workflow", task.workflow_id or task.task_id

    def _object_label(self, task: UnifiedAnalysisTask) -> str:
        params = task.task_params or {}
        if task.task_type in (AnalysisTaskType.STOCK_ANALYSIS, AnalysisTaskType.ETF_ANALYSIS):
            symbol = params.get("symbol") or params.get("stock_code") or "当前标的"
            return f"{symbol} "
        if task.task_type == AnalysisTaskType.POSITION_ANALYSIS:
            position_id = params.get("position_id") or "当前持仓"
            return f"{position_id} "
        if task.task_type == AnalysisTaskType.TRADE_REVIEW:
            return "本次交易 "
        return "当前流程 "

    def _extract_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("content", "text", "summary", "report", "analysis"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    return text.strip()
            return str(value)
        return str(value).strip()

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """去除 Markdown 格式标记，保留纯文本内容。"""
        import re
        # 去除代码块
        text = re.sub(r'```[\s\S]*?```', ' ', text)
        # 去除行内代码
        text = re.sub(r'`[^`]+`', lambda m: m.group(0).strip('`'), text)
        # 去除表格分隔行 |---|---|
        text = re.sub(r'\|[\s\-:]+\|[\s\-:|]*', ' ', text)
        # 去除表格行开头和结尾的 |
        text = re.sub(r'^\s*\||\|\s*$', ' ', text, flags=re.MULTILINE)
        # 去除表格内部的 | 分隔符
        text = re.sub(r'\|', '，', text)
        # 去除标题标记 ##
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        # 去除加粗 **text** 和 __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        # 去除斜体 *text* 和 _text_（注意不要误伤下划线变量名）
        text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', text)
        # 去除列表标记 - 和 *
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        # 去除有序列表标记 1.
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # 去除 emoji
        text = re.sub(r'[📊📈📉🔍✅❌⚠️💡🎯🔥📋🔑💰📌🏆🔧⬆⬇➡️▲▼●◆■□★☆]', '', text)
        # 去除图片和链接语法
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
        # 压缩多余空白
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()

    def _summarize_text(self, value: str, limit: int = 180) -> str:
        text = self._extract_text(value)
        # 先去除 Markdown 格式标记，再做摘要截断
        text = self._strip_markdown(text)
        text = text.replace("\r", " ").replace("\n", " ").strip()
        # 压缩连续空格
        import re
        text = re.sub(r' {2,}', ' ', text)
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _get_value(self, data: Dict[str, Any], key: str) -> Any:
        value = data.get(key)
        if value is not None:
            return value
        return getattr(data, key, None)

    def _list_value(self, data: Dict[str, Any], key: str) -> List[str]:
        value = self._get_value(data, key)
        if isinstance(value, list):
            return [self._extract_text(item) for item in value if self._extract_text(item)]
        if value:
            return [self._extract_text(value)]
        return []

    def _serialize_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        serialized: Dict[str, Any] = {}
        for key, value in doc.items():
            if key == "_id":
                continue
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, list):
                serialized[key] = [self._serialize_doc(item) if isinstance(item, dict) else item for item in value]
            elif isinstance(value, dict):
                serialized[key] = self._serialize_doc(value)
            else:
                serialized[key] = value
        return serialized

    async def _execute_suggested_action(self, user_id: str, suggestion_doc: Dict[str, Any]) -> Dict[str, Any]:
        suggested_action = suggestion_doc.get("suggested_action") or {}
        target = suggested_action.get("target")
        mode = suggested_action.get("mode")
        payload = suggested_action.get("payload") or {}

        if target == "workflow_generation" and mode == "start_session":
            try:
                from app.pro.services.workflow_generation_service import WorkflowGenerationService

                service = WorkflowGenerationService(db=self.db)
                description = payload.get("description") or suggestion_doc.get("summary") or suggestion_doc.get("title")
                session_result = await service.start_session(description=description, user_id=user_id)
                return {
                    "status": "triggered",
                    "target": target,
                    "mode": mode,
                    "session_id": session_result.get("session_id"),
                    "ai_message": session_result.get("ai_message"),
                }
            except Exception as exc:
                logger.warning(f"⚠️ 接受成长建议后触发工作流优化会话失败: {exc}")
                return {
                    "status": "failed",
                    "target": target,
                    "mode": mode,
                    "error": str(exc),
                }

        return {
            "status": "accepted_only",
            "target": target,
            "mode": mode,
        }

    async def _sync_approved_memory_to_mem0(self, memory_doc: Dict[str, Any]) -> None:
        """将已批准的成长记忆桥接到 mem0。

        该桥接采用 best-effort 策略：失败仅记录日志，不影响 Mongo 审批结果。
        """
        try:
            from core.memory.service import get_memory_service

            scope = self._map_growth_memory_to_mem0_scope(memory_doc)
            agent_id = self._resolve_growth_memory_agent_id(memory_doc)
            metadata = self._build_growth_memory_mem0_metadata(memory_doc, scope)
            content = self._build_growth_memory_mem0_content(memory_doc)

            memory_svc = get_memory_service(self.db)
            result = await memory_svc.store(
                [{"role": "assistant", "content": content}],
                user_id=str(memory_doc.get("user_id") or ""),
                agent_id=agent_id,
                session_id=str(memory_doc.get("source_id") or ""),
                scope=scope,
                metadata=metadata,
                infer=True,
            )

            if not result.success:
                logger.warning(
                    "⚠️ 成长记忆桥接 mem0 失败: memory_id=%s error=%s",
                    memory_doc.get("memory_id"),
                    result.error or "unknown",
                )
                return

            logger.info(
                "✅ 成长记忆已桥接到 mem0: memory_id=%s scope=%s facts=%s",
                memory_doc.get("memory_id"),
                scope,
                result.facts_extracted,
            )
        except Exception as exc:
            logger.warning(
                "⚠️ 成长记忆桥接 mem0 异常: memory_id=%s error=%s",
                memory_doc.get("memory_id"),
                exc,
            )

    def _map_growth_memory_to_mem0_scope(self, memory_doc: Dict[str, Any]) -> str:
        raw_scope = memory_doc.get("scope")
        task_type = str(memory_doc.get("task_type") or "")

        if raw_scope == GrowthMemoryScope.USER_PREFERENCE.value:
            return MemoryScope.USER_PREFERENCE.value
        if raw_scope == GrowthMemoryScope.PATTERN.value:
            if task_type == str(AnalysisTaskType.TRADE_REVIEW):
                return MemoryScope.TRADE_PATTERN.value
            return MemoryScope.AGENT_EXPERIENCE.value
        if raw_scope in {
            GrowthMemoryScope.OBJECT_TRACKING.value,
            GrowthMemoryScope.RESEARCH_ASSET.value,
        }:
            return MemoryScope.ANALYSIS_INSIGHT.value
        return MemoryScope.AGENT_EXPERIENCE.value

    def _resolve_growth_memory_agent_id(self, memory_doc: Dict[str, Any]) -> str:
        structured_payload = memory_doc.get("structured_payload") or {}
        agent_name = structured_payload.get("agent_name")
        if agent_name:
            return str(agent_name)
        return "workflow_growth"

    def _build_growth_memory_mem0_metadata(self, memory_doc: Dict[str, Any], mem0_scope: str) -> Dict[str, Any]:
        object_type = str(memory_doc.get("object_type") or "")
        object_key = str(memory_doc.get("object_key") or "")
        metadata: Dict[str, Any] = {
            "scope": mem0_scope,
            "source": "workflow_growth",
            "growth_memory_id": str(memory_doc.get("memory_id") or ""),
            "growth_scope": str(memory_doc.get("scope") or ""),
            "source_type": str(memory_doc.get("source_type") or ""),
            "source_id": str(memory_doc.get("source_id") or ""),
            "task_type": str(memory_doc.get("task_type") or ""),
            "workflow_id": str(memory_doc.get("workflow_id") or ""),
            "object_type": object_type,
            "object_key": object_key,
            "review_level": str(memory_doc.get("review_level") or ""),
            "confidence": memory_doc.get("confidence") or 0.0,
            "confirmed_by": str(memory_doc.get("confirmed_by") or ""),
            "confirmed_at": self._format_optional_datetime(memory_doc.get("confirmed_at")),
        }
        if object_type == "stock" and object_key:
            metadata["symbol"] = object_key
        structured_payload = memory_doc.get("structured_payload") or {}
        if structured_payload:
            metadata["structured_payload"] = structured_payload
        evidence_refs = memory_doc.get("evidence_refs") or []
        if evidence_refs:
            metadata["evidence_refs"] = evidence_refs
        return metadata

    def _build_growth_memory_mem0_content(self, memory_doc: Dict[str, Any]) -> str:
        parts: List[str] = []
        title = self._extract_text(memory_doc.get("title"))
        summary = self._extract_text(memory_doc.get("summary"))
        content = self._extract_text(memory_doc.get("content"))
        object_key = self._extract_text(memory_doc.get("object_key"))
        growth_scope = self._extract_text(memory_doc.get("scope"))

        if title:
            parts.append(f"标题: {title}")
        if object_key:
            parts.append(f"对象: {object_key}")
        if growth_scope:
            parts.append(f"成长记忆范围: {growth_scope}")
        if summary:
            parts.append(f"摘要: {summary}")
        if content:
            parts.append(f"详情: {content}")

        return "\n".join(parts)

    @staticmethod
    def _format_optional_datetime(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value or "")


_workflow_growth_service: Optional[WorkflowGrowthService] = None


def get_workflow_growth_service() -> WorkflowGrowthService:
    global _workflow_growth_service
    if _workflow_growth_service is None:
        _workflow_growth_service = WorkflowGrowthService()
    return _workflow_growth_service


def build_recall_context_sync(
    user_id: str,
    ticker: Optional[str] = None,
    workflow_id: Optional[str] = None,
    max_items: int = 10,
    max_chars: int = 3000,
) -> str:
    """
    同步版本的记忆召回，供同步工作流执行路径使用。
    通过 pymongo 同步查询，避免在非 asyncio 线程中调用异步代码。
    """
    from app.core.database import get_mongo_db_sync

    db = get_mongo_db_sync()
    collection = db.agent_memory_items

    recall_items: List[Dict[str, Any]] = []

    base_query: Dict[str, Any] = {
        "user_id": user_id,
        "status": GrowthMemoryStatus.APPROVED.value,
    }

    if ticker:
        obj_query = {**base_query, "object_key": ticker}
        docs = list(
            collection.find(obj_query).sort("updated_at", -1).limit(max_items)
        )
        recall_items.extend(docs)

    remaining = max_items - len(recall_items)

    if remaining > 0 and workflow_id:
        wf_query = {
            **base_query,
            "scope": GrowthMemoryScope.PATTERN.value,
            "workflow_id": workflow_id,
        }
        seen_ids = {str(d.get("_id")) for d in recall_items}
        docs = list(
            collection.find(wf_query).sort("updated_at", -1).limit(remaining)
        )
        for d in docs:
            if str(d.get("_id")) not in seen_ids:
                recall_items.append(d)

    remaining = max_items - len(recall_items)

    if remaining > 0:
        ra_query = {
            **base_query,
            "scope": GrowthMemoryScope.RESEARCH_ASSET.value,
        }
        seen_ids = {str(d.get("_id")) for d in recall_items}
        docs = list(
            collection.find(ra_query).sort("updated_at", -1).limit(remaining)
        )
        for d in docs:
            if str(d.get("_id")) not in seen_ids:
                recall_items.append(d)

    if not recall_items:
        return ""

    lines = ["## 历史研究记忆（已审核批准）\n"]
    total_chars = 0
    for item in recall_items:
        title = item.get("title", "")
        summary = item.get("summary") or item.get("content", "")
        scope = item.get("scope", "")
        obj_key = item.get("object_key", "")

        if len(summary) > 500:
            summary = summary[:500] + "…"

        entry = f"- **{title}**"
        if obj_key:
            entry += f" [{obj_key}]"
        if scope:
            entry += f" ({scope})"
        entry += f"\n  {summary}\n"

        if total_chars + len(entry) > max_chars:
            break
        lines.append(entry)
        total_chars += len(entry)

    return "\n".join(lines)