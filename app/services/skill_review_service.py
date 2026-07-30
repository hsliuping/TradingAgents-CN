"""Skill 生成 HITL 审核服务（v3.6.0 项6 路径B/C）。

路径B（Agent 工坊自动补齐）和路径C（AI 工作流批量生成）生成的 Skill
原本会自动绑定到 Agent，用户对生成内容没有掌控感。本服务提供"生成后审核才绑定"
机制：生成完成后写入 `skill_review_queue` 集合，等待用户确认后再触发绑定。

设计要点：
- 不阻塞主流程：写入 review queue 失败时只记日志，不让生成流程回滚
- 不自动删除被拒绝的 Skill：留在 `external_skills` 集合（status=unbound），可后续复用
- 区分来源：source_path=agent_workshop / ai_workflow，便于前端分类展示
- 路径B 确认时调用 `AgentWorkshopService.build_version()` 构建版本
- 路径C 确认时调用 `SkillOrchestrator._bind_one()` 绑定单个 skill

参考: docs/05-design/v3.0/architecture-optimization-reflection.md §6.1
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# MongoDB 集合名
REVIEW_COLLECTION = "skill_review_queue"
SKILL_COLLECTION = "external_skills"

# 审核状态
STATUS_PENDING = "pending_user_review"
STATUS_CONFIRMED = "confirmed_bound"
STATUS_REJECTED = "rejected_unbound"
STATUS_EXPIRED = "expired"

# 来源路径
SOURCE_AGENT_WORKSHOP = "agent_workshop"  # 路径B
SOURCE_AI_WORKFLOW = "ai_workflow"        # 路径C

# 待审核超时时间（小时）：超过后需重新生成/审核
PENDING_TIMEOUT_HOURS = 24


class SkillReviewService:
    """Skill 生成 HITL 审核服务。

    负责：
    1. 生成完成后写入待审核记录（路径B/C 都调用此服务）
    2. 列出待审核记录供前端展示
    3. 用户确认后触发实际绑定
    4. 用户拒绝后标记为 unbound，Skill 留在工坊
    """

    def __init__(self, db):
        """
        Args:
            db: MongoDB 异步数据库实例 (motor.motor_asyncio.AsyncIOMotorDatabase)
        """
        self._db = db

    @staticmethod
    def is_expired(item: Dict[str, Any]) -> bool:
        """判断待审核记录是否已过期（超过 PENDING_TIMEOUT_HOURS 小时）。"""
        if not item:
            return False
        created_at = item.get("created_at")
        if not created_at:
            return False
        try:
            from datetime import datetime, timezone, timedelta
            # 兼容 ISO 字符串
            if isinstance(created_at, str):
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, datetime):
                created_dt = created_at
            else:
                return False
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - created_dt > timedelta(hours=PENDING_TIMEOUT_HOURS)
        except Exception:
            return False

    @staticmethod
    def _normalize_for_api(item: Dict[str, Any]) -> Dict[str, Any]:
        """将内部存储格式映射为前端 API 契约格式。

        主要处理字段名和状态值的差异：
        - status: pending_user_review -> pending_review
        - code_preview -> code_snippet
        - test_result_summary -> test_summary（对象）
        - reviewer_user_id -> reviewer
        - review_action_note -> review_note
        """
        if not item:
            return item

        normalized = dict(item)

        # 状态值统一为前端契约
        status = normalized.get("status")
        if status == STATUS_PENDING:
            normalized["status"] = "pending_review"

        # 字段名映射
        if "code_preview" in normalized and "code_snippet" not in normalized:
            normalized["code_snippet"] = normalized.pop("code_preview")

        # test_result_summary -> test_summary（兼容旧字符串记录）
        test_summary = normalized.pop("test_result_summary", None)
        if isinstance(test_summary, dict):
            normalized["test_summary"] = test_summary
        elif isinstance(test_summary, str) and test_summary:
            # 旧数据：把字符串解析为对象
            normalized["test_summary"] = {
                "passed": "通过" in test_summary or "分数" in test_summary,
                "score": None,
                "details": {"raw": test_summary},
                "error": "",
            }
            # 尝试提取分数
            import re
            m = re.search(r"评估分数[:：]\s*([\d.]+)", test_summary)
            if m:
                try:
                    normalized["test_summary"]["score"] = float(m.group(1))
                except ValueError:
                    pass
        else:
            normalized["test_summary"] = None

        if "reviewer_user_id" in normalized and "reviewer" not in normalized:
            normalized["reviewer"] = normalized.pop("reviewer_user_id")

        if "review_action_note" in normalized and "review_note" not in normalized:
            normalized["review_note"] = normalized.pop("review_action_note")

        # source_label：前端如果没有传，组件内部会根据 source_path 生成
        if normalized.get("source_path") == SOURCE_AGENT_WORKSHOP:
            normalized["source_label"] = "Agent 工坊自动补齐"
        elif normalized.get("source_path") == SOURCE_AI_WORKFLOW:
            normalized["source_label"] = "AI 工作流批量生成"

        # target_agent_name fallback：前端会用 target_agent_id 兜底
        target_agent_id = normalized.get("target_agent_id") or ""
        if target_agent_id and not normalized.get("target_agent_name"):
            normalized["target_agent_name"] = target_agent_id

        # 过期标记（仅 pending 状态需要）
        if normalized.get("status") in (STATUS_PENDING, "pending_review"):
            normalized["is_expired"] = SkillReviewService.is_expired(item)

        return normalized

    # ================================================================
    # 写入待审核记录
    # ================================================================

    async def create_pending_reviews_for_workshop(
        self,
        *,
        workshop_session_id: str,
        agent_spec_id: str,
        agent_name: str,
        user_id: str,
        successful_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """路径B：为 Agent 工坊自动补齐的 Skill 写入待审核记录。

        Args:
            workshop_session_id: Agent 工坊会话 ID
            agent_spec_id: Agent 规格 ID
            agent_name: Agent 名称
            user_id: 发起用户 ID
            successful_items: resolve_agent_workshop_blocking_gaps 返回的 successful 列表，
                              每项含 skill_tool_id / skill_display_name / gap_description 等

        Returns:
            写入的 review 记录列表（不含 _id）
        """
        if not successful_items:
            return []

        reviews: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()

        for item in successful_items:
            tool_id = str(item.get("skill_tool_id") or "").strip()
            if not tool_id:
                logger.warning(
                    "[SkillReview][Workshop] 跳过无 tool_id 的项: gap=%s",
                    item.get("gap_description"),
                )
                continue

            # 拉取代码片段与测试摘要（失败不阻塞）
            code_preview, test_summary = await self._fetch_skill_meta(tool_id)

            review_doc = {
                "review_id": f"review_{uuid.uuid4().hex[:16]}",
                "tool_id": tool_id,
                "display_name": str(item.get("skill_display_name") or tool_id),
                "description": str(item.get("gap_description") or ""),
                "source_path": SOURCE_AGENT_WORKSHOP,
                # 路径B 上下文
                "workshop_session_id": str(workshop_session_id),
                "agent_spec_id": str(agent_spec_id),
                "agent_name": str(agent_name),
                "workflow_session_id": "",
                "workflow_id": "",
                "target_agent_id": "",
                # 通用
                "user_id": str(user_id),
                "status": STATUS_PENDING,
                "code_preview": code_preview,
                "test_result_summary": test_summary,
                "gap_description": str(item.get("gap_description") or ""),
                "gap_id": str(item.get("gap_id") or ""),
                "skill_session_id": str(item.get("session_id") or ""),
                "created_at": now,
                "reviewed_at": None,
                "reviewer_user_id": None,
                "review_action_note": "",
                "extra_metadata": {
                    "elapsed_seconds": item.get("elapsed_seconds"),
                    "pipeline_stage": item.get("pipeline_stage"),
                },
            }

            try:
                await self._db[REVIEW_COLLECTION].update_one(
                    {"review_id": review_doc["review_id"]},
                    {"$set": review_doc},
                    upsert=True,
                )
                reviews.append(review_doc)
                logger.info(
                    "[SkillReview][Workshop] 已写入待审核记录: tool_id=%s agent=%s review_id=%s",
                    tool_id, agent_name, review_doc["review_id"],
                )
            except Exception as exc:
                logger.warning(
                    "[SkillReview][Workshop] 写入失败（不阻塞生成流程）: tool_id=%s err=%s",
                    tool_id, exc,
                )

        return reviews

    async def create_pending_reviews_for_workflow(
        self,
        *,
        workflow_session_id: str,
        workflow_id: str,
        user_id: str,
        skill_results: List[Dict[str, Any]],
        blueprint=None,
    ) -> List[Dict[str, Any]]:
        """路径C：为 AI 工作流批量生成的 Skill 写入待审核记录。

        Args:
            workflow_session_id: AI 工作流生成会话 ID
            workflow_id: 工作流 ID
            user_id: 发起用户 ID
            skill_results: create_missing_skills 返回的结果列表，
                          每项含 skill_name / status / skill_id
            blueprint: WorkflowBlueprint（用于查找 target_agent_id）

        Returns:
            写入的 review 记录列表
        """
        if not skill_results:
            return []

        # 从蓝图建立 skill_name → target_agent_id 映射
        skill_to_agent: Dict[str, str] = {}
        if blueprint is not None and getattr(blueprint, "gap_analysis", None):
            for req in blueprint.gap_analysis.missing_skills or []:
                if req.skill_name and req.target_agent_id:
                    skill_to_agent[req.skill_name] = req.target_agent_id

        reviews: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()

        for result in skill_results:
            if result.get("status") != "completed":
                continue  # 失败的 skill 不写入审核队列

            tool_id = str(result.get("skill_id") or "").strip()
            skill_name = str(result.get("skill_name") or tool_id)
            if not tool_id:
                continue

            code_preview, test_summary = await self._fetch_skill_meta(tool_id)
            target_agent_id = skill_to_agent.get(skill_name, "")

            review_doc = {
                "review_id": f"review_{uuid.uuid4().hex[:16]}",
                "tool_id": tool_id,
                "display_name": skill_name,
                "description": str(result.get("skill_description") or ""),
                "source_path": SOURCE_AI_WORKFLOW,
                # 路径C 上下文
                "workshop_session_id": "",
                "agent_spec_id": "",
                "agent_name": "",
                "workflow_session_id": str(workflow_session_id),
                "workflow_id": str(workflow_id),
                "target_agent_id": target_agent_id,
                # 通用
                "user_id": str(user_id),
                "status": STATUS_PENDING,
                "code_preview": code_preview,
                "test_result_summary": test_summary,
                "gap_description": "",
                "gap_id": "",
                "skill_session_id": "",
                "created_at": now,
                "reviewed_at": None,
                "reviewer_user_id": None,
                "review_action_note": "",
                "extra_metadata": {
                    "skipped": bool(result.get("skipped")),
                },
            }

            try:
                await self._db[REVIEW_COLLECTION].update_one(
                    {"review_id": review_doc["review_id"]},
                    {"$set": review_doc},
                    upsert=True,
                )
                reviews.append(review_doc)
                logger.info(
                    "[SkillReview][Workflow] 已写入待审核记录: tool_id=%s target_agent=%s review_id=%s",
                    tool_id, target_agent_id, review_doc["review_id"],
                )
            except Exception as exc:
                logger.warning(
                    "[SkillReview][Workflow] 写入失败（不阻塞生成流程）: tool_id=%s err=%s",
                    tool_id, exc,
                )

        return reviews

    # ================================================================
    # 查询
    # ================================================================

    async def list_pending(
        self,
        session_id: str,
        source_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出指定会话的待审核 Skill。

        Args:
            session_id: 工坊会话 ID 或工作流会话 ID
            source_path: 过滤来源（agent_workshop / ai_workflow），None 表示全部

        Returns:
            待审核记录列表（按创建时间倒序，不含 _id）
        """
        query: Dict[str, Any] = {"status": STATUS_PENDING}
        # 路径B 用 workshop_session_id，路径C 用 workflow_session_id
        query["$or"] = [
            {"workshop_session_id": str(session_id)},
            {"workflow_session_id": str(session_id)},
        ]
        if source_path:
            query["source_path"] = source_path

        cursor = self._db[REVIEW_COLLECTION].find(query).sort("created_at", -1)
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(self._normalize_for_api(doc))
        return items

    async def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """按 review_id 获取单条审核记录。"""
        doc = await self._db[REVIEW_COLLECTION].find_one({"review_id": review_id})
        if doc:
            doc.pop("_id", None)
            return self._normalize_for_api(doc)
        return None

    async def find_pending_by_tool_id(
        self,
        session_id: str,
        tool_id: str,
    ) -> Optional[Dict[str, Any]]:
        """按会话+tool_id 查找待审核记录。"""
        query = {
            "tool_id": str(tool_id),
            "status": STATUS_PENDING,
            "$or": [
                {"workshop_session_id": str(session_id)},
                {"workflow_session_id": str(session_id)},
            ],
        }
        doc = await self._db[REVIEW_COLLECTION].find_one(query)
        if doc:
            doc.pop("_id", None)
            return self._normalize_for_api(doc)
        return None

    # ================================================================
    # 确认 / 拒绝
    # ================================================================

    async def confirm(
        self,
        session_id: str,
        tool_id: str,
        user_id: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """确认绑定：标记为已确认并触发实际绑定。

        路径B：调用 `AgentWorkshopService.build_version()` 构建包含该 Skill 的 Agent 版本
        路径C：调用 `SkillOrchestrator._bind_one()` 绑定到 target_agent_id

        Returns:
            {"status": "confirmed_bound", "tool_id": ..., "binding_result": ...}
        """
        review = await self.find_pending_by_tool_id(session_id, tool_id)
        if not review:
            return {
                "status": "not_found",
                "message": f"未找到会话 {session_id} 中 tool_id={tool_id} 的待审核记录",
            }

        # 检查是否已过期：超过 24h 的 pending 记录不允许再确认绑定
        if self.is_expired(review):
            return {
                "status": "expired",
                "tool_id": tool_id,
                "review_id": review.get("review_id", ""),
                "message": f"该 Skill 审核请求已超过 {PENDING_TIMEOUT_HOURS} 小时，请重新生成后再审核。",
            }

        now = datetime.utcnow().isoformat()
        source_path = review.get("source_path", "")
        binding_result: Dict[str, Any] = {}

        try:
            if source_path == SOURCE_AGENT_WORKSHOP:
                binding_result = await self._bind_for_workshop(review)
            elif source_path == SOURCE_AI_WORKFLOW:
                binding_result = await self._bind_for_workflow(review)
            else:
                binding_result = {"status": "skipped", "reason": f"未知 source_path={source_path}"}
        except Exception as exc:
            logger.error(
                "[SkillReview][Confirm] 绑定失败 tool_id=%s source=%s: %s",
                tool_id, source_path, exc, exc_info=True,
            )
            binding_result = {"status": "failed", "error": str(exc)}
            return {
                "status": "binding_failed",
                "tool_id": tool_id,
                "review_id": review.get("review_id", ""),
                "binding_result": binding_result,
                "error": str(exc),
            }

        # 更新审核记录状态
        try:
            await self._db[REVIEW_COLLECTION].update_one(
                {"review_id": review["review_id"]},
                {"$set": {
                    "status": STATUS_CONFIRMED,
                    "reviewed_at": now,
                    "reviewer_user_id": str(user_id),
                    "review_action_note": str(note),
                    "binding_result": binding_result,
                }},
            )
        except Exception as exc:
            logger.warning("[SkillReview][Confirm] 更新审核记录失败: %s", exc)

        logger.info(
            "[SkillReview][Confirm] 已确认绑定: tool_id=%s source=%s binding=%s",
            tool_id, source_path, binding_result.get("status"),
        )
        return {
            "status": STATUS_CONFIRMED,
            "tool_id": tool_id,
            "review_id": review["review_id"],
            "binding_result": binding_result,
        }

    async def reject(
        self,
        session_id: str,
        tool_id: str,
        user_id: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """拒绝绑定：标记为已拒绝，Skill 留在 `external_skills` 集合（status=unbound）。

        不会删除 Skill，用户可后续在 Skill 工坊手动复用。
        对于路径B，会同步清理 workshop_session 中 gap_report 的 generated_skill_id，
        避免后续 build_version 时仍然绑定该 skill。

        Returns:
            {"status": "rejected_unbound", "tool_id": ...}
        """
        review = await self.find_pending_by_tool_id(session_id, tool_id)
        if not review:
            return {
                "status": "not_found",
                "message": f"未找到会话 {session_id} 中 tool_id={tool_id} 的待审核记录",
            }

        # v3.6.0 fix：拒绝时也检查过期（与 confirm 保持一致）
        if self.is_expired(review):
            return {
                "status": "expired",
                "tool_id": tool_id,
                "review_id": review.get("review_id", ""),
                "message": f"该 Skill 审核请求已超过 {PENDING_TIMEOUT_HOURS} 小时，已自动过期。",
            }

        now = datetime.utcnow().isoformat()
        source_path = review.get("source_path", "")

        # 路径B：清理 workshop_session gap_report 中对应 skill 的 generated_skill_id
        # 防止后续 build_version 时仍然把它绑定进去
        if source_path == SOURCE_AGENT_WORKSHOP:
            workshop_session_id = review.get("workshop_session_id", "")
            if workshop_session_id:
                try:
                    await self._clear_workshop_gap_binding(workshop_session_id, tool_id)
                except Exception as exc:
                    logger.warning(
                        "[SkillReview][Reject] 清理 workshop gap_report 失败（不阻塞）: %s",
                        exc,
                    )

        # 把 external_skills 中的 skill 标记为 unbound（不删除）
        try:
            await self._db[SKILL_COLLECTION].update_one(
                {"tool_id": tool_id, "status": {"$in": ["draft", "active"]}},
                {"$set": {
                    "status": "unbound",
                    "updated_at": now,
                    "rejection_reason": str(note)[:1000] if note else "",
                }},
            )
        except Exception as exc:
            logger.warning(
                "[SkillReview][Reject] 标记 external_skills status=unbound 失败（不阻塞）: %s",
                exc,
            )

        # 更新审核记录状态
        try:
            await self._db[REVIEW_COLLECTION].update_one(
                {"review_id": review["review_id"]},
                {"$set": {
                    "status": STATUS_REJECTED,
                    "reviewed_at": now,
                    "reviewer_user_id": str(user_id),
                    "review_action_note": str(note),
                }},
            )
        except Exception as exc:
            logger.warning("[SkillReview][Reject] 更新审核记录失败: %s", exc)

        logger.info(
            "[SkillReview][Reject] 已拒绝绑定: tool_id=%s source=%s",
            tool_id, source_path,
        )
        return {
            "status": STATUS_REJECTED,
            "tool_id": tool_id,
            "review_id": review["review_id"],
        }

    # ================================================================
    # 内部：实际绑定逻辑
    # ================================================================

    async def _bind_for_workshop(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """路径B 确认：调用 AgentWorkshopService.build_version 构建版本。

        build_version 会读取 workshop_session.gap_report 中所有 generated_skill_id
        已确认的 skill 会保留 generated_skill_id，被拒绝的已被 _clear_workshop_gap_binding 清理。
        """
        workshop_session_id = review.get("workshop_session_id", "")
        if not workshop_session_id:
            return {"status": "skipped", "reason": "缺少 workshop_session_id"}

        from app.services.agent_workshop_service import AgentWorkshopService
        ws_service = AgentWorkshopService(db=self._db)
        build_result = await ws_service.build_version(workshop_session_id)

        version = build_result.get("version") if isinstance(build_result, dict) else None
        version_id = ""
        if isinstance(version, dict):
            version_id = str(version.get("version_id") or "")

        return {
            "status": "built_version",
            "workshop_session_id": workshop_session_id,
            "version_id": version_id,
            "build_result_status": build_result.get("status") if isinstance(build_result, dict) else "",
        }

    async def _bind_for_workflow(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """路径C 确认：调用 SkillOrchestrator._bind_one 绑定到 target_agent_id。"""
        target_agent_id = str(review.get("target_agent_id") or "").strip()
        tool_id = str(review.get("tool_id") or "").strip()
        if not target_agent_id:
            return {"status": "skipped", "reason": "缺少 target_agent_id"}
        if not tool_id:
            return {"status": "skipped", "reason": "缺少 tool_id"}

        from core.workflow.generator.skill_orchestrator import SkillOrchestrator
        orch = SkillOrchestrator(self._db)
        # v3.6.0 项6 路径C：用户已确认，绑定立即激活（is_active=True）
        await orch._bind_one(target_agent_id, tool_id, is_active=True)

        # 同时把 external_skills 状态从 draft 切回 active（路径C 生成时被标记为 draft）
        now = datetime.utcnow().isoformat()
        try:
            await self._db[SKILL_COLLECTION].update_one(
                {"tool_id": tool_id, "status": "draft"},
                {"$set": {"status": "active", "updated_at": now}},
            )
        except Exception as exc:
            logger.warning(
                "[SkillReview][Confirm][Workflow] 切换 skill 状态 draft→active 失败: %s",
                exc,
            )

        return {
            "status": "bound",
            "tool_id": tool_id,
            "target_agent_id": target_agent_id,
        }

    async def _clear_workshop_gap_binding(
        self, workshop_session_id: str, tool_id: str
    ) -> None:
        """路径B 拒绝时：清理 workshop_session 中 gap_report 对应 skill 的绑定信息。

        直接操作 MongoDB（避免循环依赖 AgentWorkshopService 的内部方法），
        把 gap_report.resolved_gaps 中匹配 tool_id 的项的 generated_skill_id 置空、status 改回 pending。
        """
        session_col = "agent_workshop_sessions"
        doc = await self._db[session_col].find_one({"session_id": workshop_session_id})
        if not doc:
            return

        gap_report = doc.get("gap_report") or {}
        modified = False

        # blocking_gaps 可能是 list[str]，不包含 tool_id，跳过
        # resolved_gaps 是 list[dict]，包含 skill_tool_id
        resolved_gaps = gap_report.get("resolved_gaps") or []
        for item in resolved_gaps:
            if not isinstance(item, dict):
                continue
            if str(item.get("skill_tool_id") or "") == tool_id:
                item["skill_tool_id"] = None
                item["skill_display_name"] = None
                item["status"] = "pending"
                modified = True

        if modified:
            await self._db[session_col].update_one(
                {"session_id": workshop_session_id},
                {"$set": {"gap_report": gap_report}},
            )
            logger.info(
                "[SkillReview] 已清理 workshop_session=%s 中 tool_id=%s 的绑定信息",
                workshop_session_id, tool_id,
            )

    # ================================================================
    # 内部：拉取 Skill 元数据
    # ================================================================

    async def _fetch_skill_meta(self, tool_id: str) -> tuple[str, Dict[str, Any]]:
        """从 external_skills 拉取代码片段和测试摘要。

        Returns:
            (code_preview, test_result_summary)
            code_preview: 代码前 2000 字符（前端展示用）
            test_result_summary: 结构化测试结果摘要
                {
                    "passed": bool,
                    "score": float | None,
                    "details": Dict[str, Any],
                    "error": str,
                }
        """
        try:
            doc = await self._db[SKILL_COLLECTION].find_one(
                {"tool_id": tool_id},
                {"code": 1, "final_score": 1, "generation_rounds": 1,
                 "generation_time": 1, "metadata": 1, "display_name": 1,
                 "status": 1},
            )
        except Exception as exc:
            logger.warning("[SkillReview] 拉取 skill 元数据失败 tool_id=%s: %s", tool_id, exc)
            return ("", {"passed": False, "score": None, "details": {}, "error": "拉取元数据失败"})

        if not doc:
            return ("", {"passed": False, "score": None, "details": {}, "error": "Skill 不存在"})

        code = str(doc.get("code") or "")
        code_preview = code[:2000] if len(code) > 2000 else code

        meta = doc.get("metadata") or {}
        score = doc.get("final_score")
        rounds = doc.get("generation_rounds")
        time_seconds = doc.get("generation_time")

        # 判断测试是否通过：分数 >= 6.0 认为通过（与 Skill 生成管线一致）
        passed = False
        if score is not None:
            try:
                passed = float(score) >= 6.0
            except (ValueError, TypeError):
                pass

        details: Dict[str, Any] = {}
        if score is not None:
            details["score"] = score
        if rounds is not None:
            details["rounds"] = rounds
        if time_seconds is not None:
            details["generation_time_seconds"] = time_seconds

        ctx = meta.get("generation_context") if isinstance(meta.get("generation_context"), dict) else {}
        if ctx.get("test_pass_rate") is not None:
            details["test_pass_rate"] = ctx["test_pass_rate"]

        # 保留 human-readable 摘要，方便直接展示
        parts: List[str] = []
        if score is not None:
            parts.append(f"评估分数: {score}")
        if rounds is not None:
            parts.append(f"迭代轮数: {rounds}")
        if time_seconds is not None:
            parts.append(f"生成耗时: {time_seconds}s")
        if details.get("test_pass_rate") is not None:
            parts.append(f"测试通过率: {details['test_pass_rate']}")
        if parts:
            details["summary_text"] = " | ".join(parts)

        test_result_summary = {
            "passed": passed,
            "score": score,
            "details": details,
            "error": "",
        }
        return (code_preview, test_result_summary)

    async def expire_stale_reviews(self, hours: int = None) -> int:
        """清理超时的待审核 Skill 记录（默认 PENDING_TIMEOUT_HOURS 小时）。

        v3.6.0 fix：将超过时限的 pending 记录标记为 expired，防止僵尸审核记录堆积。

        Args:
            hours: 超时小时数，默认使用类常量 PENDING_TIMEOUT_HOURS

        Returns:
            过期的记录数量
        """
        if hours is None:
            hours = PENDING_TIMEOUT_HOURS
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            result = await self._db[REVIEW_COLLECTION].update_many(
                {
                    "status": STATUS_PENDING,
                    "created_at": {"$lt": cutoff.isoformat()},
                },
                {"$set": {
                    "status": STATUS_EXPIRED,
                    "reviewed_at": datetime.utcnow().isoformat(),
                    "review_action_note": "system_auto_expired",
                }},
            )
            if result.modified_count > 0:
                logger.info(
                    "[SkillReview] 已自动过期 %d 条待审核记录（超过 %dh）",
                    result.modified_count, hours,
                )
            return result.modified_count
        except Exception as exc:
            logger.warning("[SkillReview] expire_stale_reviews 失败: %s", exc)
            return 0
