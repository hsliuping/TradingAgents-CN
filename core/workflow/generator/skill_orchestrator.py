"""
Skill 编排器 — 根据蓝图中的 Skill 缺口，自动创建并绑定缺失的工具

流程:
1. 遍历 blueprint.gap_analysis.missing_skills
2. 对每个 SkillCreationRequest:
   a. 调用 SkillGenerationService.start_session(description)
   b. 自动 confirm_spec → 触发代码生成 + 验证
   c. 成功 → 回填 generated_skill_id + 绑定到 target_agent_id
   d. 失败 → 标记 status=failed，记录错误
3. 将所有新创建的 Skill 绑定到对应 Agent

参考: docs/05-design/v3.0/ai-workflow-generation.md §4.4
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .workflow_spec import SkillCreationRequest, WorkflowBlueprint

logger = logging.getLogger(__name__)

# 单个 Skill 创建超时上限（秒），超过则标记为 failed
SKILL_CREATION_TIMEOUT = 120


class SkillOrchestrator:
    """
    Skill 编排器

    根据蓝图中的 gap_analysis.missing_skills，
    批量调用 SkillGenerationService 管线创建缺失的工具，
    并将其绑定到对应 Agent。
    """

    def __init__(self, db, skill_generation_service=None):
        """
        Args:
            db: MongoDB 异步数据库实例 (motor)
            skill_generation_service: SkillGenerationService 实例
                如果不传，将在首次使用时按需创建
        """
        self._db = db
        self._skill_service = skill_generation_service

    def _ensure_service(self):
        """延迟初始化 SkillGenerationService"""
        if self._skill_service is None:
            from app.services.skill_generation_service import SkillGenerationService
            self._skill_service = SkillGenerationService(db=self._db)

    # ================================================================
    # 公开方法
    # ================================================================

    async def create_missing_skills(
        self,
        blueprint: WorkflowBlueprint,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        批量创建蓝图中标记为缺失的 Skill

        Args:
            blueprint: AI 生成的工作流蓝图（含 gap_analysis.missing_skills）
            user_id: 发起人 ID

        Returns:
            每个 Skill 的创建结果列表:
            [{"skill_name", "status", "skill_id"?, "error"?}]
        """
        if not blueprint.gap_analysis:
            logger.info("[SkillOrchestrator] 无缺口分析，跳过 Skill 创建")
            return []

        missing = blueprint.gap_analysis.missing_skills
        if not missing:
            logger.info("[SkillOrchestrator] 无缺失 Skill")
            return []

        self._ensure_service()

        results: List[Dict[str, Any]] = []
        for req in missing:
            result = await self._create_one_skill(req, user_id, blueprint)
            results.append(result)

        # 更新蓝图进度
        completed = sum(1 for r in results if r["status"] == "completed")
        blueprint.creation_progress["skills_completed"] = completed

        return results

    async def bind_skills_to_agents(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
    ) -> int:
        """
        将新创建的 Skill 绑定到对应 Agent（通过 tool_agent_bindings）

        只处理 status=completed 且有 generated_skill_id 的 Skill。
        绑定级别：Agent 级别（无 node_id），作为默认保底。

        Args:
            workflow_id: 工作流 ID（用于日志）
            blueprint: 蓝图

        Returns:
            成功绑定的数量
        """
        if not blueprint.gap_analysis:
            return 0

        bound_count = 0
        for req in blueprint.gap_analysis.missing_skills:
            if req.status != "completed" or not req.generated_skill_id:
                continue
            if not req.target_agent_id:
                continue

            try:
                await self._bind_one(req.target_agent_id, req.generated_skill_id)
                bound_count += 1
                logger.info(
                    f"[SkillOrchestrator] ✅ 已绑定 {req.generated_skill_id} → {req.target_agent_id}"
                )
            except Exception as e:
                logger.error(
                    f"[SkillOrchestrator] ❌ 绑定失败 {req.generated_skill_id} → {req.target_agent_id}: {e}",
                    exc_info=True,
                )

        return bound_count

    async def bind_additional_tools_to_nodes(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
        is_active: bool = False,
    ) -> int:
        """
        为 agent_reshaping 中的 additional_tools 创建节点级别工具绑定。

        对于同一 Agent 在不同节点出现的场景，通过 workflow_id + node_id 精确绑定，
        避免工具污染其他节点。

        Args:
            workflow_id: 工作流 ID
            blueprint: 蓝图（含 agent_reshaping 列表）
            is_active: 是否激活绑定（False=草稿，True=生产）

        Returns:
            成功创建的绑定数量
        """
        if not blueprint.gap_analysis or not blueprint.gap_analysis.agent_reshaping:
            return 0

        bound_count = 0
        now = datetime.utcnow().isoformat()

        for reshaping in blueprint.gap_analysis.agent_reshaping:
            if not reshaping.additional_tools:
                continue
            if not reshaping.node_id:
                logger.warning(
                    f"[SkillOrchestrator] ⚠️ agent_reshaping 中 {reshaping.agent_id} 缺少 node_id，"
                    f"跳过节点级工具绑定（additional_tools={reshaping.additional_tools}）"
                )
                continue

            for tool_id in reshaping.additional_tools:
                try:
                    await self._db.tool_agent_bindings.update_one(
                        {
                            "agent_id": reshaping.agent_id,
                            "tool_id": tool_id,
                            "workflow_id": workflow_id,
                            "node_id": reshaping.node_id,
                        },
                        {
                            "$set": {
                                "agent_id": reshaping.agent_id,
                                "tool_id": tool_id,
                                "workflow_id": workflow_id,
                                "node_id": reshaping.node_id,
                                "priority": 10,
                                "is_active": is_active,
                                "updated_at": now,
                            },
                            "$setOnInsert": {
                                "created_at": now,
                            },
                        },
                        upsert=True,
                    )
                    bound_count += 1
                    logger.info(
                        f"[SkillOrchestrator] ✅ 节点级工具绑定: "
                        f"{tool_id} → {reshaping.agent_id} "
                        f"(workflow={workflow_id}, node={reshaping.node_id}, active={is_active})"
                    )
                except Exception as e:
                    logger.error(
                        f"[SkillOrchestrator] ❌ 节点级工具绑定失败: "
                        f"{tool_id} → {reshaping.agent_id}: {e}",
                        exc_info=True,
                    )

        return bound_count

    # ================================================================
    # 内部方法
    # ================================================================

    async def _create_one_skill(
        self,
        req: SkillCreationRequest,
        user_id: str,
        blueprint: WorkflowBlueprint,
    ) -> Dict[str, Any]:
        """
        创建单个 Skill

        流程:
        1. 检查同名 Skill 是否已存在 → 跳过
        2. start_session(description) → 开始创建会话
        3. confirm_spec(session_id) → 触发代码生成
        4. 成功 → 回填 req.generated_skill_id，修改 req.status
        5. 失败 → 标记 req.status='failed'，记录 req.error
        """
        skill_name = req.skill_name

        # 1. 检查同名 Skill 是否已存在
        existing = await self._db.external_skills.find_one(
            {"tool_id": skill_name, "status": "active"}
        )
        if existing:
            req.generated_skill_id = existing["tool_id"]
            req.status = "completed"
            logger.info(
                f"[SkillOrchestrator] ⏭️ Skill '{skill_name}' 已存在，跳过创建"
            )
            return {
                "skill_name": skill_name,
                "status": "completed",
                "skill_id": existing["tool_id"],
                "skipped": True,
            }

        # 2. 开始创建会话（传入蓝图上下文，让 Skill 工坊理解大背景）
        req.status = "creating"
        description = self._build_skill_description(req, blueprint)

        try:
            start_result = await self._skill_service.start_session(
                description=description,
                user_id=user_id,
            )
            session_id = start_result.get("session_id")
            if not session_id:
                raise ValueError("start_session 未返回 session_id")

            logger.info(
                f"[SkillOrchestrator] 🚀 开始创建 Skill '{skill_name}' (session: {session_id})"
            )

            # 3. 自动确认并生成代码
            confirm_result = await self._skill_service.confirm_spec(
                session_id=session_id,
                user_message="确认，请直接生成代码",
            )

            if confirm_result.get("success"):
                skill_id = confirm_result.get("skill_id", "")
                req.generated_skill_id = skill_id
                req.status = "completed"

                # 将新创建的 Skill 标记为 draft 状态，避免污染生产数据
                # 发布时再统一切换为 active
                try:
                    await self._db.external_skills.update_one(
                        {"tool_id": skill_id},
                        {"$set": {"status": "draft"}},
                    )
                except Exception as draft_err:
                    logger.warning(
                        f"[SkillOrchestrator] 标记 Skill '{skill_id}' 为 draft 失败: {draft_err}"
                    )

                logger.info(
                    f"[SkillOrchestrator] ✅ Skill '{skill_name}' 创建成功(draft): {skill_id}"
                )
                return {
                    "skill_name": skill_name,
                    "status": "completed",
                    "skill_id": skill_id,
                }
            else:
                error = confirm_result.get("error", "代码生成失败")
                req.status = "failed"
                req.error = error
                logger.warning(
                    f"[SkillOrchestrator] ⚠️ Skill '{skill_name}' 生成失败: {error}"
                )
                return {
                    "skill_name": skill_name,
                    "status": "failed",
                    "error": error,
                }

        except Exception as e:
            req.status = "failed"
            req.error = str(e)
            logger.error(
                f"[SkillOrchestrator] ❌ Skill '{skill_name}' 创建异常: {e}",
                exc_info=True,
            )
            return {
                "skill_name": skill_name,
                "status": "failed",
                "error": str(e),
            }

    async def _bind_one(self, agent_id: str, tool_id: str, *, is_active: bool = False) -> None:
        """
        将一个 Skill 绑定到 Agent（upsert 到 tool_agent_bindings）

        Args:
            agent_id: 目标 Agent ID
            tool_id: 要绑定的 Skill/工具 ID
            is_active: 是否立即激活（默认 False 为草稿状态，发布后激活）
        """
        now = datetime.utcnow().isoformat()
        await self._db.tool_agent_bindings.update_one(
            {"agent_id": agent_id, "tool_id": tool_id},
            {
                "$set": {
                    "agent_id": agent_id,
                    "tool_id": tool_id,
                    "is_active": is_active,
                    "priority": 99,  # 新创建的 Skill 优先级较低
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

    @staticmethod
    def _build_skill_description(req: SkillCreationRequest, blueprint: WorkflowBlueprint) -> str:
        """
        将 SkillCreationRequest 转为 SkillGenerationService 可用的自然语言描述

        包含完整上下文：工作流背景 + Agent 角色 + 工具需求，
        确保 Skill 工坊的代码生成流水线能理解大背景。
        """
        parts = []

        # ── 工作流背景 ──
        wf_name = blueprint.name or ""
        wf_desc = blueprint.description or blueprint.summary or ""
        if wf_name or wf_desc:
            parts.append("## 工作流背景")
            if wf_name:
                parts.append(f"- 工作流名称: {wf_name}")
            if wf_desc:
                parts.append(f"- 工作流目的: {wf_desc}")

        # ── 目标 Agent 在本工作流中的角色 ──
        agent_context_parts = SkillOrchestrator._find_agent_context(req, blueprint)
        if agent_context_parts:
            parts.append("")
            parts.append("## 目标 Agent 在本工作流中的角色")
            parts.append(f"- Agent ID: {req.target_agent_id}")
            for line in agent_context_parts:
                parts.append(f"- {line}")

        # ── 工具需求本身 ──
        parts.append("")
        parts.append("## 需要创建的工具")
        parts.append(f"- 工具名称: {req.skill_name}")
        if req.skill_description:
            parts.append(f"- 功能描述: {req.skill_description}")
        parts.append(f"- 使用场景: 供 {req.target_agent_id} Agent 在上述工作流中使用")

        result = "\n".join(parts)
        logger.info(
            f"[SkillOrchestrator] 📝 Skill 创建描述 ({req.skill_name}, "
            f"长度={len(result)} 字符)"
        )
        return result

    @staticmethod
    def _find_agent_context(
        req: SkillCreationRequest, blueprint: WorkflowBlueprint
    ) -> List[str]:
        """
        从蓝图中提取目标 Agent 在本工作流中的角色上下文

        优先级：
        1. agent_reshaping（LLM 生成的角色重塑方案，信息最丰富）
        2. nodes（节点的 label 和 description）
        """
        context: List[str] = []

        # 1. 从 agent_reshaping 获取角色重塑信息
        if blueprint.gap_analysis:
            for reshaping in blueprint.gap_analysis.agent_reshaping:
                if reshaping.agent_id == req.target_agent_id:
                    if reshaping.new_role:
                        context.append(f"角色定位: {reshaping.new_role}")
                    if reshaping.reshaping_direction:
                        context.append(f"定制方向: {reshaping.reshaping_direction}")
                    if reshaping.key_focus_areas:
                        areas = ", ".join(reshaping.key_focus_areas)
                        context.append(f"关键分析维度: {areas}")
                    break

        # 2. 从节点补充节点级别的信息
        for node in blueprint.nodes:
            if node.agent_id == req.target_agent_id:
                if node.label:
                    # 避免重复（agent_reshaping 可能已经有类似信息）
                    if not any("节点名称" in c for c in context):
                        context.insert(0, f"节点名称: {node.label}")
                if node.description:
                    context.append(f"节点说明: {node.description}")
                break

        return context

