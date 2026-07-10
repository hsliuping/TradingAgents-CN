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
                self._llm_client = UnifiedLLMClient.from_config(config)
                logger.info(
                    f"[WorkflowGen] LLM 客户端初始化: "
                    f"provider={config.provider}, model={config.model}, timeout={config.timeout}s"
                )
                return self._llm_client
        except Exception as e:
            logger.warning(f"[WorkflowGen] 获取推理模型失败, 回退到默认: {e}")

        # 回退到 provider
        self._llm_client = UnifiedLLMClient.from_provider(
            self._provider, model=self._model, timeout=self._LLM_TIMEOUT
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

        # 收集资源上下文
        resource_context = (await self._collector.collect_all())["context_text"]

        # 第一轮对话
        planner = await self._ensure_planner()
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

        resource_context = (await self._collector.collect_all())["context_text"]
        planner = await self._ensure_planner()
        session, ai_message = planner.chat(session, user_message, resource_context)

        await self._save_session(session)

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
        self, session_id: str, message: str = "确认"
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
        resource_context = (await self._collector.collect_all())["context_text"]
        planner = await self._ensure_planner()
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

        # 4a. 提示词自动补全
        prompt_gen = await self._ensure_prompt_gen()
        created_prompt_ids: List[str] = []
        try:
            created_prompt_ids = await prompt_gen.generate_prompts(
                workflow_id=workflow_id, blueprint=blueprint
            )
            session.created_prompt_ids = created_prompt_ids
        except Exception as e:
            logger.error(f"[WorkflowGen] 提示词生成异常: {e}", exc_info=True)

        # 4b. Skill 自动创建
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

        # 4c. Skill 绑定（将新创建的 Skill 绑定到 Agent 级别）
        bindings_created = 0
        try:
            bindings_created = await self._skill_orch.bind_skills_to_agents(
                workflow_id=workflow_id, blueprint=blueprint
            )
        except Exception as e:
            logger.error(f"[WorkflowGen] Skill 绑定异常: {e}", exc_info=True)

        # 4d. 节点级工具绑定（将 agent_reshaping.additional_tools 绑定到对应节点）
        try:
            node_bindings = await self._skill_orch.bind_additional_tools_to_nodes(
                workflow_id=workflow_id, blueprint=blueprint, is_active=False
            )
            bindings_created += node_bindings
            if node_bindings:
                logger.info(f"[WorkflowGen] ✅ 创建节点级工具绑定: {node_bindings} 条")
        except Exception as e:
            logger.error(f"[WorkflowGen] 节点级工具绑定异常: {e}", exc_info=True)

        # 5. 转换 Blueprint → WorkflowDefinition 并保存
        session.status = GenerationSessionStatus.CREATING
        await self._save_session(session)

        try:
            wf_data = self._blueprint_to_workflow_dict(blueprint, workflow_id)
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

        return {
            "status": "completed",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "blueprint_summary": blueprint.summary,
            "creation_report": creation_report,
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
        resource_context = (await self._collector.collect_all())["context_text"]
        planner = await self._ensure_planner()
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
        resource_context = (await self._collector.collect_all())["context_text"]
        planner = await self._ensure_planner()
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

    async def publish(self, session_id: str) -> Dict[str, Any]:
        """
        发布草稿资源为正式版本

        将 AI 生成的提示词、Skill、绑定和工作流从 draft 状态激活为 active，
        使其在生产环境中生效。
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
        if skill_ids:
            r = await self._db.external_skills.update_many(
                {"tool_id": {"$in": skill_ids}, "status": "draft"},
                {"$set": {"status": "active", "updated_at": now.isoformat()}},
            )
            published_counts["skills"] = r.modified_count

        # 3. 激活工具绑定 is_active: false → true
        # 包含两类绑定：
        #   a) 新创建 Skill 的 Agent 级别绑定（通过 tool_id 过滤）
        #   b) agent_reshaping.additional_tools 的节点级别绑定（通过 workflow_id 过滤）
        if skill_ids:
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
            f"skills={published_counts['skills']}, "
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
            "message": "工作流及关联资源已发布为正式版本",
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
    # 蓝图 → 工作流定义 转换
    # ================================================================

    def _blueprint_to_workflow_dict(
        self, blueprint: WorkflowBlueprint, workflow_id: str
    ) -> Dict[str, Any]:
        """
        将 AI 蓝图转换为标准 WorkflowDefinition 字典

        PlannedNode → NodeDefinition 格式
        PlannedEdge → EdgeDefinition 格式
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
                "type": "normal",
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

