"""
AI 工作流架构师 — 服务层

会话管理 + MongoDB 持久化 + 业务编排。
整合 ResourceCollector / WorkflowPlanner / PromptGenerator / SkillOrchestrator 四大核心模块。

参考: docs/05-design/v3.0/ai-workflow-generation.md §5
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.llm import UnifiedLLMClient
from core.workflow.generator import (
    ResourceCollector,
    WorkflowPlanner,
    PromptGenerator,
    SkillOrchestrator,
    WorkflowGenerationSession,
    WorkflowBlueprint,
    GenerationSessionStatus,
    ConversationRound,
    GapAnalysisResult,
    SkillCreationRequest,
    AgentReshapingPlan,
)

logger = logging.getLogger(__name__)

# MongoDB 集合名
SESSION_COLLECTION = "workflow_generation_sessions"


class WorkflowGenerationService:
    """
    AI 工作流架构师服务

    提供对话式需求沟通、蓝图生成、自动补全（提示词/Skill）、
    工作流创建和迭代优化的完整业务逻辑。
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        self._db = db
        self._provider = provider
        self._model = model
        self._llm_client = llm_client

        # 核心模块（延迟初始化 LLM 相关）
        self._collector = ResourceCollector(db)
        self._planner: Optional[WorkflowPlanner] = None
        self._prompt_gen: Optional[PromptGenerator] = None
        self._skill_orch = SkillOrchestrator(db)
        self._capability_index = None  # 延迟初始化

    # ================================================================
    # 延迟初始化
    # ================================================================

    # 工作流生成需要处理大量上下文（33+ Agent、100+ Tool、Skill 列表），
    # 深度推理模型可能需要较长时间，默认 60s 不够用。
    _LLM_TIMEOUT = 600  # 10 分钟

    async def _ensure_llm_client(self) -> UnifiedLLMClient:
        """确保 LLM 客户端已初始化"""
        if self._llm_client:
            return self._llm_client

        # 从数据库获取推理模型配置
        try:
            from app.services.intelligent_assistant_service import get_reasoning_llm_config
            config = await get_reasoning_llm_config(self._db)
            if config:
                # 覆盖 timeout：蓝图生成需要更长的推理时间
                config.timeout = max(config.timeout, self._LLM_TIMEOUT)
                # 覆盖 max_tokens：蓝图 JSON 输出可能较长，设置更大的值
                config.max_tokens = max(config.max_tokens or 0, 8192)
                self._llm_client = UnifiedLLMClient.from_config(config)
                logger.info(
                    f"[WorkflowGen] LLM 客户端初始化: "
                    f"provider={config.provider}, model={config.model}, timeout={config.timeout}s, max_tokens={config.max_tokens}"
                )
                return self._llm_client
        except Exception as e:
            logger.warning(f"[WorkflowGen] 获取推理模型失败, 回退到默认: {e}")

        # 回退到 provider
        self._llm_client = UnifiedLLMClient.from_provider(
            self._provider, model=self._model, timeout=self._LLM_TIMEOUT, max_tokens=8192
        )
        return self._llm_client

    async def _ensure_planner(self) -> WorkflowPlanner:
        """确保 Planner 已初始化"""
        if self._planner is None:
            client = await self._ensure_llm_client()
            self._planner = WorkflowPlanner(llm_client=client)
        return self._planner

    async def _ensure_prompt_gen(self) -> PromptGenerator:
        """确保 PromptGenerator 已初始化"""
        if self._prompt_gen is None:
            client = await self._ensure_llm_client()
            self._prompt_gen = PromptGenerator(
                db=self._db, llm_client=client
            )
        return self._prompt_gen

    async def _ensure_capability_index(self):
        """确保 CapabilityIndexService 已初始化（延迟加载）"""
        if self._capability_index is None:
            from app.services.capability_index_service import CapabilityIndexService
            try:
                self._capability_index = CapabilityIndexService(self._db)
                await self._capability_index.ensure_index()
            except Exception as e:
                logger.warning(
                    "[WorkflowGen] CapabilityIndex 初始化失败，Agent 过滤降级为全部返回: %s", e
                )
                self._capability_index = None
        return self._capability_index

    # ================================================================
    # 阶段 1-2：对话式需求沟通
    # ================================================================

    async def start_session(
        self, description: str, user_id: str = ""
    ) -> Dict[str, Any]:
        """
        开始创建会话

        1. 创建 WorkflowGenerationSession
        2. 收集可用资源
        3. 调用 WorkflowPlanner.chat() 处理第一轮
        4. 保存到 MongoDB
        5. 返回 session_id + AI 回复
        """
        # 创建会话
        session = WorkflowGenerationSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            status=GenerationSessionStatus.GATHERING,
        )

        # 收集资源上下文 + 结构化 agents
        resources = await self._collector.collect_all(user_query=description, capability_index=await self._ensure_capability_index())
        resource_context = resources["context_text"]
        available_agents = resources.get("agents", [])

        # 第一轮对话
        planner = await self._ensure_planner()
        planner.set_available_agents(available_agents)
        session, ai_message = planner.chat(session, description, resource_context)

        # 持久化
        await self._save_session(session)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "status": session.status.value,
            "current_round": session.current_round,
        }

    async def respond(
        self, session_id: str, user_message: str
    ) -> Dict[str, Any]:
        """
        用户回复（继续对话）
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.status not in (
            GenerationSessionStatus.GATHERING,
            GenerationSessionStatus.PLANNING,
        ):
            raise ValueError(f"会话状态 {session.status.value} 不允许继续对话")

        resources = await self._collector.collect_all(user_query=user_message, capability_index=await self._ensure_capability_index())
        resource_context = resources["context_text"]
        available_agents = resources.get("agents", [])

        planner = await self._ensure_planner()
        planner.set_available_agents(available_agents)
        session, ai_message = planner.chat(session, user_message, resource_context)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "status": session.status.value,
            "current_round": session.current_round,
        }

    # ================================================================
    # 阶段 3-4：确认 → 蓝图生成 → 自动补全 → 创建
    # ================================================================

    async def confirm_and_create(
        self, session_id: str, message: str = "确认",
        workflow_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        确认方案并执行完整创建流程

        1. 生成 WorkflowBlueprint
        2. 提示词自动补全
        3. Skill 自动创建 + 绑定
        4. 转换为 WorkflowDefinition 并保存
        5. 返回 workflow_id + 创建报告
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        # 提前生成 workflow_id（提示词需要引用）
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        # 3. 生成蓝图
        session.status = GenerationSessionStatus.PLANNING
        # 用所有用户消息构建查询，用于 Agent 相关性过滤
        user_query = " ".join(r.user_message for r in session.rounds if r.user_message)
        resources = await self._collector.collect_all(user_query=user_query, capability_index=await self._ensure_capability_index())
        resource_context = resources["context_text"]
        available_agents = resources.get("agents", [])

        planner = await self._ensure_planner()
        planner.set_available_agents(available_agents)
        session, blueprint = planner.generate_blueprint(session, resource_context)

        if not blueprint:
            session.status = GenerationSessionStatus.FAILED
            session.error = "蓝图生成失败"
            await self._save_session(session)
            return {
                "status": "failed",
                "session_id": session_id,
                "error": "蓝图生成失败，请重试或调整需求描述",
            }

        session.blueprint = blueprint
        session.blueprint_confirmed = True
        session.status = GenerationSessionStatus.COMPLETING
        await self._save_session(session)

        # 4. Capability-based 缺口分析（为每个 Agent 搜索匹配工具）
        await self._run_capability_gap_analysis(blueprint)

        # 5a. 提示词自动补全
        prompt_gen = await self._ensure_prompt_gen()
        created_prompt_ids: List[str] = []
        try:
            created_prompt_ids = await prompt_gen.generate_prompts(
                workflow_id=workflow_id, blueprint=blueprint
            )
            session.created_prompt_ids = created_prompt_ids
        except Exception as e:
            logger.error(f"[WorkflowGen] 提示词生成异常: {e}", exc_info=True)

        # 5b. Skill 自动创建
        skill_results: List[Dict[str, Any]] = []
        try:
            skill_results = await self._skill_orch.create_missing_skills(
                blueprint=blueprint, user_id=session.user_id
            )
            session.created_skill_ids = [
                r["skill_id"] for r in skill_results
                if r.get("status") == "completed" and r.get("skill_id")
            ]
        except Exception as e:
            logger.error(f"[WorkflowGen] Skill 创建异常: {e}", exc_info=True)

        # 5c. v3.6.0 项6 路径C：Skill 绑定改为待用户审核
        # 原来：bind_skills_to_agents 自动绑定到 Agent 级别
        # 现在：写入 skill_review_queue，等待用户调用 confirm/reject API
        # 用户确认后才绑定到 Agent；拒绝则 Skill 留在工坊（status=unbound）
        pending_skill_reviews: List[Dict[str, Any]] = []
        try:
            from app.services.skill_review_service import SkillReviewService
            review_service = SkillReviewService(db=self._db)
            pending_skill_reviews = await review_service.create_pending_reviews_for_workflow(
                workflow_session_id=session_id,
                workflow_id=workflow_id,
                user_id=session.user_id,
                skill_results=skill_results,
                blueprint=blueprint,
            )
            if pending_skill_reviews:
                logger.info(
                    f"[WorkflowGen] ✅ 已写入 {len(pending_skill_reviews)} 条 Skill 待审核记录，"
                    f"等待用户审核后才绑定"
                )
        except Exception as e:
            logger.error(f"[WorkflowGen] Skill 待审核记录写入异常: {e}", exc_info=True)

        # 5d. 节点级工具绑定（将 agent_reshaping.additional_tools 绑定到对应节点）
        # 注意：这是已有工具的节点级绑定，不是新生成 Skill 的绑定，不受路径C HITL 影响
        bindings_created = 0
        try:
            node_bindings = await self._skill_orch.bind_additional_tools_to_nodes(
                workflow_id=workflow_id, blueprint=blueprint, is_active=False
            )
            bindings_created += node_bindings
            if node_bindings:
                logger.info(f"[WorkflowGen] ✅ 创建节点级工具绑定: {node_bindings} 条")
        except Exception as e:
            logger.error(f"[WorkflowGen] 节点级工具绑定异常: {e}", exc_info=True)

        # 6. 转换 Blueprint → WorkflowDefinition 并保存
        session.status = GenerationSessionStatus.CREATING
        await self._save_session(session)

        try:
            wf_data = self._blueprint_to_workflow_dict(blueprint, workflow_id, workflow_type=workflow_type)
            from core.api import WorkflowAPI
            api = WorkflowAPI()
            result = api.create(wf_data, user_id=session.user_id or None)

            if not result.get("success"):
                raise ValueError(result.get("errors", ["创建工作流失败"]))

            session.workflow_id = workflow_id
            session.status = GenerationSessionStatus.COMPLETED
        except Exception as e:
            session.status = GenerationSessionStatus.FAILED
            session.error = str(e)
            logger.error(f"[WorkflowGen] 工作流创建失败: {e}", exc_info=True)
            await self._save_session(session)
            return {
                "status": "failed",
                "session_id": session_id,
                "error": f"工作流创建失败: {e}",
            }

        # 构建创建报告并持久化到 session
        creation_report = self._build_creation_report(
            blueprint, created_prompt_ids, skill_results, bindings_created
        )
        session.creation_report = creation_report
        await self._save_session(session)

        # 自动发布：将提示词、Skill、绑定、工作流从 draft 激活为 active
        # 用户在对话阶段已确认方案，confirm_and_create 即为最终确认，
        # 无需额外手动点击"发布"按钮
        # v3.6.0 项6 路径C：如果有待审核的 Skill，跳过 Skill 自动发布，等待用户审核
        has_pending_skill_reviews = bool(pending_skill_reviews)
        publish_result = {}
        try:
            publish_result = await self.publish(
                session_id,
                skip_skill_publishing=has_pending_skill_reviews,
            )
            logger.info(
                f"[WorkflowGen] ✅ 自动发布完成: "
                f"prompts={publish_result.get('published_prompts', 0)}, "
                f"skills={publish_result.get('published_skills', 0)}"
                f"{'(skipped, pending review)' if has_pending_skill_reviews else ''}, "
                f"bindings={publish_result.get('published_bindings', 0)}, "
                f"workflow={publish_result.get('workflow_published', False)}"
            )
        except Exception as e:
            logger.error(f"[WorkflowGen] 自动发布失败（不影响工作流创建结果）: {e}", exc_info=True)

        return {
            "status": "completed",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "blueprint_summary": blueprint.summary,
            "creation_report": creation_report,
            "published": True,
            "publish_result": publish_result,
            # v3.6.0 项6 路径C：待用户审核的 Skill 列表
            "pending_user_review": {
                "count": len(pending_skill_reviews),
                "tool_ids": [r.get("tool_id") for r in pending_skill_reviews if r.get("tool_id")],
                "review_ids": [r.get("review_id") for r in pending_skill_reviews if r.get("review_id")],
                "next_action": (
                    "用户审核后调用 "
                    "/api/agent-workshop/skill-review/{session_id}/{tool_id}/confirm 或 /reject"
                    if pending_skill_reviews
                    else ""
                ),
            },
        }

    # ================================================================
    # 阶段 6：迭代优化
    # ================================================================

    async def optimize(
        self, session_id: str, feedback: str
    ) -> Dict[str, Any]:
        """
        迭代优化已创建的工作流
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.status not in (
            GenerationSessionStatus.COMPLETED,
            GenerationSessionStatus.OPTIMIZING,
        ):
            raise ValueError(f"会话状态 {session.status.value} 不允许优化")

        session.status = GenerationSessionStatus.OPTIMIZING
        resources = await self._collector.collect_all(user_query=feedback, capability_index=await self._ensure_capability_index())
        resource_context = resources["context_text"]
        available_agents = resources.get("agents", [])

        planner = await self._ensure_planner()
        planner.set_available_agents(available_agents)
        session, ai_message = planner.generate_optimization(
            session, feedback, resource_context
        )

        # optimize_count 已在 planner.generate_optimization 内部递增，此处不再重复
        await self._save_session(session)

        return {
            "session_id": session_id,
            "ai_message": ai_message,
            "status": session.status.value,
            "optimization_round": session.optimize_count,
        }

    async def confirm_optimization(
        self, session_id: str
    ) -> Dict[str, Any]:
        """
        确认优化方案并应用

        重新生成蓝图、更新提示词、更新工作流
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.status != GenerationSessionStatus.OPTIMIZING:
            raise ValueError("只有优化中的会话才能确认优化")

        workflow_id = session.workflow_id
        if not workflow_id:
            raise ValueError("会话没有关联的工作流，无法优化")

        # 重新生成蓝图
        user_query = " ".join(r.user_message for r in session.rounds if r.user_message)
        resources = await self._collector.collect_all(user_query=user_query, capability_index=await self._ensure_capability_index())
        resource_context = resources["context_text"]
        available_agents = resources.get("agents", [])

        planner = await self._ensure_planner()
        planner.set_available_agents(available_agents)
        session, blueprint = planner.generate_blueprint(session, resource_context)

        if not blueprint:
            return {
                "status": "failed",
                "session_id": session_id,
                "error": "优化蓝图生成失败",
            }

        session.blueprint = blueprint

        # 重新生成提示词
        prompt_gen = await self._ensure_prompt_gen()
        created_prompt_ids: List[str] = []
        try:
            created_prompt_ids = await prompt_gen.generate_prompts(
                workflow_id=workflow_id, blueprint=blueprint
            )
            session.created_prompt_ids = list(
                set(session.created_prompt_ids + created_prompt_ids)
            )
        except Exception as e:
            logger.error(f"[WorkflowGen] 优化提示词生成异常: {e}", exc_info=True)

        # 更新工作流定义
        try:
            wf_data = self._blueprint_to_workflow_dict(blueprint, workflow_id)
            from core.api import WorkflowAPI
            api = WorkflowAPI()
            result = api.update(workflow_id, wf_data, user_id=session.user_id or None)

            if not result.get("success"):
                raise ValueError(result.get("errors", ["更新工作流失败"]))
        except Exception as e:
            logger.error(f"[WorkflowGen] 工作流更新失败: {e}", exc_info=True)
            return {
                "status": "failed",
                "session_id": session_id,
                "error": f"工作流更新失败: {e}",
            }

        # 构建优化后的创建报告并持久化
        creation_report = self._build_creation_report(
            blueprint, created_prompt_ids, [], 0
        )
        session.creation_report = creation_report
        session.status = GenerationSessionStatus.COMPLETED
        await self._save_session(session)

        return {
            "status": "completed",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "optimization_round": session.optimize_count,
            "creation_report": creation_report,
        }

    # ================================================================
    # 会话管理
    # ================================================================

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情"""
        doc = await self._db[SESSION_COLLECTION].find_one(
            {"session_id": session_id}
        )
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def list_sessions(
        self,
        status: Optional[str] = None,
        user_id: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出会话"""
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if status:
            statuses = [s.strip() for s in status.split(",") if s.strip()]
            if len(statuses) == 1:
                query["status"] = statuses[0]
            elif statuses:
                query["status"] = {"$in": statuses}

        total = await self._db[SESSION_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            self._db[SESSION_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def delete_session(self, session_id: str) -> bool:
        """删除会话（同时清理关联的 draft 资源）"""
        session = await self._load_session(session_id)
        if not session:
            return False

        # 仅清理未发布（draft）的资源，已发布的不动
        if session.status != GenerationSessionStatus.PUBLISHED:
            await self._cleanup_draft_resources(session)

        result = await self._db[SESSION_COLLECTION].delete_one(
            {"session_id": session_id}
        )
        return result.deleted_count > 0

    async def publish(
        self,
        session_id: str,
        skip_skill_publishing: bool = False,
    ) -> Dict[str, Any]:
        """
        发布草稿资源为正式版本

        将 AI 生成的提示词、Skill、绑定和工作流从 draft 状态激活为 active，
        使其在生产环境中生效。

        Args:
            session_id: 会话 ID
            skip_skill_publishing: v3.6.0 项6 路径C：是否跳过 Skill 发布。
                True 时 Skill 保持 draft 状态，等待用户审核后再发布。
                默认 False（保持向后兼容）。
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.status not in (
            GenerationSessionStatus.COMPLETED,
            GenerationSessionStatus.OPTIMIZING,
        ):
            raise ValueError(
                f"只能发布已完成的工作流（当前状态: {session.status}）"
            )

        workflow_id = session.workflow_id
        prompt_ids = session.created_prompt_ids or []
        skill_ids = session.created_skill_ids or []
        now = datetime.utcnow()

        published_counts = {
            "prompts": 0,
            "skills": 0,
            "bindings": 0,
            "workflow": False,
        }

        # 1. 发布提示词 draft → active
        if prompt_ids:
            oid_list = []
            for pid in prompt_ids:
                try:
                    oid_list.append(ObjectId(pid))
                except Exception:
                    pass
            if oid_list:
                r = await self._db.prompt_templates.update_many(
                    {"_id": {"$in": oid_list}, "status": "draft"},
                    {"$set": {"status": "active", "updated_at": now}},
                )
                published_counts["prompts"] = r.modified_count

        # 2. 发布 Skill draft → active
        # v3.6.0 项6 路径C：skip_skill_publishing=True 时跳过，Skill 保持 draft 等待用户审核
        if skill_ids and not skip_skill_publishing:
            r = await self._db.external_skills.update_many(
                {"tool_id": {"$in": skill_ids}, "status": "draft"},
                {"$set": {"status": "active", "updated_at": now.isoformat()}},
            )
            published_counts["skills"] = r.modified_count
        elif skip_skill_publishing and skill_ids:
            logger.info(
                f"[WorkflowGen] 跳过 {len(skill_ids)} 个 Skill 的自动发布，"
                f"等待用户审核后再发布（路径C HITL）"
            )

        # 3. 激活工具绑定 is_active: false → true
        # 包含两类绑定：
        #   a) 新创建 Skill 的 Agent 级别绑定（通过 tool_id 过滤）
        #      v3.6.0 项6 路径C：skip_skill_publishing=True 时也跳过此步（绑定由 confirm API 触发）
        #   b) agent_reshaping.additional_tools 的节点级别绑定（通过 workflow_id 过滤）
        if skill_ids and not skip_skill_publishing:
            r = await self._db.tool_agent_bindings.update_many(
                {"tool_id": {"$in": skill_ids}, "is_active": False},
                {"$set": {"is_active": True, "updated_at": now.isoformat()}},
            )
            published_counts["bindings"] += r.modified_count

        if workflow_id:
            # 激活所有属于此工作流的节点级草稿绑定（additional_tools 绑定）
            r = await self._db.tool_agent_bindings.update_many(
                {"workflow_id": workflow_id, "is_active": False},
                {"$set": {"is_active": True, "updated_at": now.isoformat()}},
            )
            published_counts["bindings"] += r.modified_count

        # 4. 发布工作流 draft → active
        if workflow_id:
            r = await self._db.workflow_definitions.update_one(
                {"id": workflow_id, "status": "draft"},
                {"$set": {"status": "active", "updated_at": now}},
            )
            published_counts["workflow"] = r.modified_count > 0

        # 5. 更新 session 状态为 published
        session.status = GenerationSessionStatus.PUBLISHED
        await self._save_session(session)

        logger.info(
            f"[WorkflowGen] ✅ 会话 {session_id} 已发布: "
            f"prompts={published_counts['prompts']}, "
            f"skills={published_counts['skills']}{'(skipped)' if skip_skill_publishing else ''}, "
            f"bindings={published_counts['bindings']}, "
            f"workflow={published_counts['workflow']}"
        )

        return {
            "session_id": session_id,
            "workflow_id": workflow_id,
            "published_prompts": published_counts["prompts"],
            "published_skills": published_counts["skills"],
            "published_bindings": published_counts["bindings"],
            "workflow_published": published_counts["workflow"],
            "skill_publishing_skipped": skip_skill_publishing,
            "message": "工作流及关联资源已发布为正式版本"
            + ("（Skill 待用户审核后发布）" if skip_skill_publishing else ""),
        }

    async def _cleanup_draft_resources(
        self, session: WorkflowGenerationSession
    ) -> None:
        """清理会话关联的草稿资源（删除 draft 状态的 prompts/skills/bindings/workflow）"""
        prompt_ids = session.created_prompt_ids or []
        skill_ids = session.created_skill_ids or []
        workflow_id = session.workflow_id

        # 删除 draft 提示词
        if prompt_ids:
            oid_list = []
            for pid in prompt_ids:
                try:
                    oid_list.append(ObjectId(pid))
                except Exception:
                    pass
            if oid_list:
                await self._db.prompt_templates.delete_many(
                    {"_id": {"$in": oid_list}, "status": "draft"}
                )

        # 删除 draft Skill
        if skill_ids:
            await self._db.external_skills.delete_many(
                {"tool_id": {"$in": skill_ids}, "status": "draft"}
            )

        # 删除未激活的绑定
        if skill_ids:
            await self._db.tool_agent_bindings.delete_many(
                {"tool_id": {"$in": skill_ids}, "is_active": False}
            )

        # 删除 draft 工作流
        if workflow_id:
            await self._db.workflow_definitions.delete_one(
                {"id": workflow_id, "status": "draft"}
            )

        logger.info(
            f"[WorkflowGen] 🗑️ 已清理 session {session.session_id} 的草稿资源: "
            f"prompts={len(prompt_ids)}, skills={len(skill_ids)}, workflow={workflow_id}"
        )

    async def get_session_history(
        self, session_id: str
    ) -> Dict[str, Any]:
        """获取完整沟通记录（含初始创建 + 优化轮次）"""
        doc = await self._db[SESSION_COLLECTION].find_one(
            {"session_id": session_id}
        )
        if not doc:
            return {"session_id": session_id, "sections": []}

        doc.pop("_id", None)
        sections = []

        # 初始创建对话
        gathering_rounds = [
            r for r in doc.get("rounds", [])
            if r.get("phase", "gathering") == "gathering"
        ]
        if gathering_rounds:
            sections.append({
                "type": "initial_creation",
                "label": "初始创建",
                "rounds": gathering_rounds,
                "created_at": doc.get("created_at", ""),
            })

        # 优化轮次
        optimize_rounds = doc.get("optimize_rounds", [])
        for idx, opt in enumerate(optimize_rounds):
            sections.append({
                "type": "optimization",
                "label": f"优化 v{idx + 2}",
                "rounds": opt if isinstance(opt, list) else [opt],
                "feedback": opt[0].get("user_message", "") if isinstance(opt, list) and opt else "",
            })

        return {
            "session_id": session_id,
            "workflow_id": doc.get("workflow_id"),
            "sections": sections,
        }

    # ================================================================
    # MongoDB 持久化
    # ================================================================

    async def _load_session(
        self, session_id: str
    ) -> Optional[WorkflowGenerationSession]:
        """从 MongoDB 加载会话"""
        doc = await self._db[SESSION_COLLECTION].find_one(
            {"session_id": session_id}
        )
        if not doc:
            return None
        doc.pop("_id", None)
        return WorkflowGenerationSession(**doc)

    async def _save_session(
        self, session: WorkflowGenerationSession
    ) -> None:
        """保存会话到 MongoDB"""
        session.updated_at = datetime.utcnow()
        session_doc = session.model_dump(mode="json")
        await self._db[SESSION_COLLECTION].update_one(
            {"session_id": session.session_id},
            {"$set": session_doc},
            upsert=True,
        )

    # ================================================================
    # Capability-based 缺口分析
    # ================================================================

    async def _run_capability_gap_analysis(
        self, blueprint: WorkflowBlueprint
    ) -> None:
        """
        使用 CapabilityIndex 为蓝图中的每个 Agent 搜索匹配的工具和 Skill。

        替代之前全量传给 LLM 的方式（300+ 工具太大），
        改为为每个 Agent 精准搜索相关工具，填充 available_tools / available_agents / missing_skills。
        """
        try:
            from app.services.capability_index_service import CapabilityIndexService
        except ImportError:
            logger.warning("[WorkflowGen] CapabilityIndexService 不可用，跳过工具匹配")
            return

        capability_index = CapabilityIndexService(self._db)
        try:
            await capability_index.ensure_index()
        except Exception as e:
            logger.warning(f"[WorkflowGen] CapabilityIndex 初始化失败: {e}, 跳过工具匹配")
            return

        if not blueprint.gap_analysis:
            blueprint.gap_analysis = GapAnalysisResult()

        gap = blueprint.gap_analysis

        # 收集蓝图中的所有 Agent（去重）
        seen_agent_ids: set = set()
        for node in blueprint.nodes:
            if node.agent_id:
                seen_agent_ids.add(node.agent_id)
        # 辩论节点可能有 participants
        for node in blueprint.nodes:
            if node.type == "debate" and node.config:
                participants = node.config.get("participants", [])
                for p in participants:
                    if isinstance(p, dict) and p.get("agent_id"):
                        seen_agent_ids.add(p["agent_id"])

        if not seen_agent_ids:
            logger.info("[WorkflowGen] 蓝图中无 Agent 节点，跳过工具匹配")
            return

        logger.info(f"[WorkflowGen] 为 {len(seen_agent_ids)} 个 Agent 搜索匹配工具")

        available_tools: List[Dict[str, str]] = []
        available_agents: List[Dict[str, str]] = []
        tool_id_set: set = set()

        # 每个 Agent 按其角色描述搜索工具
        for agent_id in sorted(seen_agent_ids):
            # 构建搜索查询：Agent 的角色描述
            query_text = self._build_agent_tool_query(agent_id, blueprint)

            try:
                hits = await capability_index.search_capabilities(
                    query=query_text or f"{agent_id} 分析工具",
                    top_k=8,
                    bindable_only=True,
                    source_types=["builtin_tool", "skill", "external_skill"],
                )
            except Exception as e:
                logger.warning(f"[WorkflowGen] 搜索 {agent_id} 工具失败: {e}")
                continue

            for hit in hits:
                cap = hit.capability
                if cap.capability_id in tool_id_set:
                    continue
                tool_id_set.add(cap.capability_id)
                available_tools.append({
                    "id": cap.capability_id,
                    "name": cap.name or cap.label or cap.capability_id,
                    "used_by_agent": agent_id,
                })

            available_agents.append({
                "id": agent_id,
                "name": agent_id,
                "role_in_workflow": self._get_agent_role(agent_id, blueprint),
            })

            logger.info(
                f"[WorkflowGen]   {agent_id}: 找到 {len(hits)} 个匹配工具"
            )

        gap.available_tools = available_tools
        gap.available_agents = available_agents

        # 分析缺口：检查 agent_reshaping 中的 additional_tools 是否需要新 Skill
        for reshaping in gap.agent_reshaping:
            for tool_name in reshaping.additional_tools:
                if tool_name not in tool_id_set:
                    existing = gap.missing_skills or []
                    if not any(s.skill_name == tool_name for s in existing):
                        gap.missing_skills.append(SkillCreationRequest(
                            skill_name=tool_name,
                            skill_description=f"为 {reshaping.new_role or reshaping.agent_id} 提供 {tool_name} 能力",
                            target_agent_id=reshaping.agent_id,
                            priority="optional",
                        ))

        # 更新分析摘要
        if not gap.analysis_summary:
            gap.analysis_summary = (
                f"共 {len(seen_agent_ids)} 个 Agent，"
                f"{len(gap.agent_reshaping)} 个需定制提示词，"
                f"找到 {len(available_tools)} 个可用工具"
                + (f"，{len(gap.missing_skills)} 个可选新 Skill" if gap.missing_skills else "")
            )

        # 更新蓝图创建进度
        blueprint.creation_progress["skills_total"] = len(gap.missing_skills)
        blueprint.creation_progress["prompts_total"] = len(gap.agent_reshaping)

        logger.info(
            f"[WorkflowGen] ✅ 工具匹配完成: {len(available_tools)} 个工具, "
            f"{len(gap.missing_skills)} 个缺失 Skill"
        )

    def _build_agent_tool_query(
        self, agent_id: str, blueprint: WorkflowBlueprint
    ) -> str:
        """为 Agent 构建工具搜索查询文本"""
        parts = [agent_id.replace("_", " ")]

        # 从 agent_reshaping 获取角色描述
        if blueprint.gap_analysis:
            for r in blueprint.gap_analysis.agent_reshaping:
                if r.agent_id == agent_id:
                    if r.new_role:
                        parts.append(r.new_role)
                    if r.reshaping_direction:
                        parts.append(r.reshaping_direction)
                    if r.key_focus_areas:
                        parts.append(" ".join(r.key_focus_areas))
                    break

        # 从节点描述获取
        for node in blueprint.nodes:
            if node.agent_id == agent_id and node.description:
                parts.append(node.description)
                break

        return " ".join(parts)[:500]

    def _get_agent_role(
        self, agent_id: str, blueprint: WorkflowBlueprint
    ) -> str:
        """获取 Agent 在工作流中的角色描述"""
        if blueprint.gap_analysis:
            for r in blueprint.gap_analysis.agent_reshaping:
                if r.agent_id == agent_id:
                    return r.new_role or r.original_role or ""
        for node in blueprint.nodes:
            if node.agent_id == agent_id:
                return node.description or node.label or ""
        return ""

    def _blueprint_to_workflow_dict(
        self, blueprint: WorkflowBlueprint, workflow_id: str,
        workflow_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将 AI 蓝图转换为标准 WorkflowDefinition 字典

        PlannedNode -> NodeDefinition 格式
        PlannedEdge -> EdgeDefinition 格式
        """
        nodes = []
        for n in blueprint.nodes:
            nodes.append({
                "id": n.id,
                "type": n.type,
                "agent_id": n.agent_id,
                "label": n.label or n.description or n.id,
                "position": {"x": n.position_x, "y": n.position_y},
                "config": n.config or {},
            })

        edges = []
        for e in blueprint.edges:
            edges.append({
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "type": e.type or "normal",
                "condition": e.condition,
                "label": e.label,
                "animated": e.animated,
            })

        tags = list(set(["ai-generated", "v2"] + (blueprint.tags or [])))

        return {
            "id": workflow_id,
            "name": blueprint.name or "AI 生成的工作流",
            "description": blueprint.description or blueprint.summary or "",
            "version": "2.0.0",
            "nodes": nodes,
            "edges": edges,
            "config": blueprint.config or {},
            "tags": tags,
            "is_template": False,
            "workflow_type": workflow_type or "stock_analysis",
            "input_config": blueprint.input_config or {"fields": []},
            "status": "draft",  # 草稿状态，发布后才变为 active
        }

    # ================================================================
    # 创建报告
    # ================================================================

    def _build_creation_report(
        self,
        blueprint: WorkflowBlueprint,
        created_prompt_ids: List[str],
        skill_results: List[Dict[str, Any]],
        bindings_created: int = 0,
    ) -> Dict[str, Any]:
        """
        构建创建报告

        包含：工作流结构、定制提示词列表、使用默认提示词列表、
        Skill 创建成功/失败列表、绑定关系
        """
        gap = blueprint.gap_analysis

        # ---- 工作流结构 ----
        workflow_structure = {
            "name": blueprint.name or "",
            "description": blueprint.description or "",
            "summary": blueprint.summary or "",
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "label": n.label or n.description or n.id,
                    "agent_id": n.agent_id or "",
                    "description": n.description or "",
                }
                for n in blueprint.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "label": e.label or "",
                }
                for e in blueprint.edges
            ],
        }

        # ---- 提示词报告 ----
        prompts_created = []
        if gap and gap.agent_reshaping:
            for idx, plan in enumerate(gap.agent_reshaping):
                prompts_created.append({
                    "agent_id": plan.agent_id,
                    "template_id": created_prompt_ids[idx]
                    if idx < len(created_prompt_ids)
                    else None,
                    "new_role": plan.new_role,
                    "reshaping_direction": plan.reshaping_direction or "",
                    "key_focus_areas": plan.key_focus_areas or [],
                })

        prompts_default = []
        if gap and gap.agents_using_default:
            prompts_default = [
                {
                    "agent_id": a.get("id", a.get("agent_id", "")),
                    "name": a.get("name", ""),
                    "reason": a.get("reason", ""),
                }
                for a in gap.agents_using_default
            ]

        # ---- Skill 报告 ----
        skills_created = [
            r for r in skill_results if r.get("status") == "completed"
        ]
        skills_failed = [
            r for r in skill_results if r.get("status") != "completed"
        ]

        # ---- 绑定关系 ----
        bindings_info = []
        if gap and gap.missing_skills:
            for req in gap.missing_skills:
                if req.status == "completed" and req.generated_skill_id:
                    bindings_info.append({
                        "skill_name": req.skill_name,
                        "skill_id": req.generated_skill_id,
                        "target_agent_id": req.target_agent_id,
                    })

        return {
            "workflow_structure": workflow_structure,
            "prompts_created": prompts_created,
            "prompts_default": prompts_default,
            "skills_created": skills_created,
            "skills_failed": skills_failed,
            "bindings_created": bindings_created,
            "bindings_info": bindings_info,
        }

