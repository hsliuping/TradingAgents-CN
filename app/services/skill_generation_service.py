"""
Skill 生成服务 — 业务逻辑层

封装 core/tools/external/ 的各模块，处理 MongoDB 持久化和异步编排。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.tools.external import (
    ConversationRound,
    ExpectedOutput,
    IterationController,
    RequirementAnalyzer,
    SkillCreationSession,
    SkillParameter,
    SkillSpec,
    SessionStatus,
    PipelineResult,
)

logger = logging.getLogger("webapi")

# MongoDB 集合名
SESSION_COLLECTION = "skill_creation_sessions"
SKILL_COLLECTION = "external_skills"


class SkillGenerationService:
    """
    Skill 生成服务

    提供需求沟通、代码生成、Skill 管理的完整业务逻辑。
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        reasoning_llm_client=None,
        coding_llm_client=None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        """
        Args:
            db: MongoDB 数据库
            reasoning_llm_client: 需求分析用（深度推理大模型），多轮对话、澄清需求
            coding_llm_client: 代码生成用（编程大模型），生成代码、Judge 评分
            provider, model: 回退用，当上述客户端均为空时使用
        """
        self._db = db
        self._provider = provider
        self._model = model
        self._analyzer = RequirementAnalyzer(
            llm_client=reasoning_llm_client, provider=provider, model=model
        )
        self._controller = IterationController(
            llm_client=coding_llm_client, provider=provider, model=model
        )

    # ==================== 需求沟通 ====================

    async def start_session(
        self, description: str, user_id: str = ""
    ) -> Dict[str, Any]:
        """
        开始创建会话：提交初始需求

        Returns:
            包含 session_id, ai_message, clarity_level 等信息的 dict
        """
        # 创建会话
        session = self._analyzer.create_session(user_id=user_id)

        # 处理第一轮输入（会做清晰度评估和边界检测）
        session, ai_message = await asyncio.get_event_loop().run_in_executor(
            None, self._analyzer.process_user_input, session, description
        )

        # 持久化到 MongoDB
        session_doc = session.model_dump(mode="json")
        await self._db[SESSION_COLLECTION].insert_one(session_doc)

        max_rounds = self._analyzer._get_max_rounds(session.clarity_level)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "clarity_level": session.clarity_level.value if session.clarity_level else "medium",
            "boundary_check": session.boundary_check.model_dump() if session.boundary_check else None,
            "current_round": session.current_round,
            "expected_rounds": max_rounds,
        }

    async def respond_to_session(
        self, session_id: str, user_message: str
    ) -> Dict[str, Any]:
        """
        用户回复对话轮次

        Returns:
            包含 ai_message, current_round, is_final_round 等信息的 dict
        """
        # 从 MongoDB 加载会话
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.spec_confirmed:
            raise ValueError("规格已确认，无法继续对话")

        # 处理用户输入
        session, ai_message = await asyncio.get_event_loop().run_in_executor(
            None, self._analyzer.process_user_input, session, user_message
        )

        # 更新 MongoDB
        await self._save_session(session)

        max_rounds = self._analyzer._get_max_rounds(session.clarity_level)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "current_round": session.current_round,
            "expected_rounds": max_rounds,
            "is_final_round": session.current_round >= max_rounds,
            "boundary_check": session.boundary_check.model_dump() if session.boundary_check else None,
        }

    async def confirm_spec(
        self, session_id: str, user_message: str = "确认"
    ) -> Dict[str, Any]:
        """
        确认规格并触发代码生成

        Returns:
            包含 status, spec, generation_result 等信息的 dict
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        # 生成 SkillSpec
        session, spec = await asyncio.get_event_loop().run_in_executor(
            None, self._analyzer.confirm_spec, session, user_message
        )

        if not spec:
            return {
                "status": "failed",
                "message": "规格生成失败，请重新描述需求",
            }

        # 更新会话状态
        session.status = SessionStatus.GENERATING
        await self._save_session(session)

        # 执行代码生成管线
        result = await asyncio.get_event_loop().run_in_executor(
            None, self._controller.run, spec
        )

        # 保存生成结果到会话
        session.status = (
            SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
        )
        session.pipeline_result = result
        await self._save_session(session)

        # 如果生成成功，保存到 external_skills 集合
        skill_id = None
        if result.success:
            skill_id = await self._save_skill(session, spec, result)

        return {
            "status": "completed" if result.success else "failed",
            "session_id": session_id,
            "skill_id": skill_id,
            "spec": spec.model_dump() if spec else None,
            "success": result.success,
            "total_rounds": result.total_rounds,
            "total_time": result.total_time,
            "final_score": (
                result.iterations[-1].eval_score.total
                if result.iterations and result.iterations[-1].eval_score
                else None
            ),
            "error": result.error,
        }

    # ==================== Skill 管理 ====================

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情"""
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def list_sessions(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出创建会话（草稿/未完成）"""
        query: Dict[str, Any] = {}
        if status:
            # 支持逗号分隔的多状态：gathering,confirmed
            statuses = [s.strip() for s in status.split(",")]
            query["status"] = {"$in": statuses}
        if user_id:
            query["user_id"] = user_id

        total = await self._db[SESSION_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size

        sessions = []
        cursor = (
            self._db[SESSION_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        async for doc in cursor:
            doc.pop("_id", None)
            sessions.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": sessions,
        }

    async def delete_session(self, session_id: str) -> bool:
        """删除草稿会话"""
        result = await self._db[SESSION_COLLECTION].delete_one({"session_id": session_id})
        return result.deleted_count > 0

    async def list_skills(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出外部 Skill（分页）"""
        query: Dict[str, Any] = {}
        if category:
            query["category"] = category
        if status:
            query["status"] = status

        total = await self._db[SKILL_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size

        skills = []
        cursor = (
            self._db[SKILL_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        async for doc in cursor:
            doc.pop("_id", None)
            skills.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": skills,
        }

    async def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """获取 Skill 详情"""
        doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def get_skill_code(self, skill_id: str) -> Optional[str]:
        """获取 Skill 源代码"""
        doc = await self._db[SKILL_COLLECTION].find_one(
            {"tool_id": skill_id}, {"code": 1}
        )
        if not doc:
            return None
        return doc.get("code", "")

    async def get_skill_history(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Skill 完整沟通历史：原始创建会话 + 所有优化会话

        Returns:
            {
                "skill_id": "...",
                "sections": [
                    { "type": "creation", "label": "创建", "session_id": "...", "rounds": [...], "created_at": "..." },
                    { "type": "optimize", "label": "优化 v2", "session_id": "...", "rounds": [...], "created_at": "...", "feedback": "..." },
                    ...
                ]
            }
        """
        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            return None

        sections = []

        # 原始创建会话
        original_session_id = skill_doc.get("session_id", "")
        if original_session_id:
            session = await self.get_session(original_session_id)
            if session:
                sections.append({
                    "type": "creation",
                    "label": "初始创建",
                    "session_id": original_session_id,
                    "rounds": session.get("rounds", []),
                    "created_at": session.get("created_at", ""),
                })

        # 所有优化会话
        optimize_ids = skill_doc.get("optimize_session_ids", [])
        # 向后兼容：如果只有旧的 optimize_session_id 字段
        legacy_id = skill_doc.get("optimize_session_id", "")
        if legacy_id and legacy_id not in optimize_ids:
            optimize_ids = [legacy_id] + optimize_ids

        for idx, opt_sid in enumerate(optimize_ids):
            session = await self.get_session(opt_sid)
            if session:
                version_label = f"优化 v{idx + 2}"
                # 从 rounds 中提取优化反馈
                feedback = ""
                rounds = session.get("rounds", [])
                if rounds:
                    first_msg = rounds[0].get("user_message", "")
                    if first_msg.startswith("[优化] "):
                        feedback = first_msg[len("[优化] "):]
                sections.append({
                    "type": "optimize",
                    "label": version_label,
                    "session_id": opt_sid,
                    "rounds": rounds,
                    "created_at": session.get("created_at", ""),
                    "feedback": feedback,
                })

        return {
            "skill_id": skill_id,
            "display_name": skill_doc.get("display_name", ""),
            "sections": sections,
        }

    async def update_skill_status(
        self, skill_id: str, new_status: str
    ) -> bool:
        """更新 Skill 状态（active / disabled / archived）"""
        result = await self._db[SKILL_COLLECTION].update_one(
            {"tool_id": skill_id},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow().isoformat()}},
        )
        return result.modified_count > 0

    async def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill"""
        result = await self._db[SKILL_COLLECTION].delete_one({"tool_id": skill_id})
        return result.deleted_count > 0

    async def test_skill(
        self, skill_id: str, test_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """手动测试 Skill"""
        doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not doc:
            raise ValueError(f"Skill {skill_id} 不存在")

        code = doc.get("code", "")
        if not code:
            raise ValueError("Skill 没有代码")

        # 使用 SandboxRunner 执行
        from core.tools.external import SandboxRunner, SkillSpec

        runner = SandboxRunner()
        # 构建简单的 spec 用于测试
        spec = SkillSpec(
            tool_id=doc["tool_id"],
            display_name=doc.get("display_name", ""),
            description=doc.get("description", ""),
            test_input=test_args or doc.get("test_input", {}),
        )
        sandbox_result = runner.run(code, spec)

        return {
            "success": sandbox_result.success,
            "output": sandbox_result.output,
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "execution_time": sandbox_result.execution_time,
            "error": sandbox_result.error,
        }

    async def optimize_skill(
        self, skill_id: str, feedback: str
    ) -> Dict[str, Any]:
        """
        优化已有 Skill：基于用户反馈重新生成代码

        流程：
        1. 加载已有 Skill 和原始 Session
        2. 将原始对话 + 当前代码 + 用户反馈 合成新的上下文
        3. 创建新 Session 记录优化过程
        4. 执行代码生成管线
        5. 成功则更新 Skill 代码，并保存优化版本号
        """
        # 加载现有 Skill
        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            raise ValueError(f"Skill {skill_id} 不存在")

        # 加载原始会话（获取原始沟通记录和 spec）
        original_session_id = skill_doc.get("session_id", "")
        original_session = None
        if original_session_id:
            original_session = await self.get_session(original_session_id)

        # 重建 SkillSpec
        params = [SkillParameter(**p) for p in skill_doc.get("parameters", [])]
        expected_output_data = skill_doc.get("expected_output", {})
        expected_output = ExpectedOutput(**expected_output_data) if expected_output_data else ExpectedOutput()

        spec = SkillSpec(
            tool_id=skill_doc["tool_id"],
            display_name=skill_doc.get("display_name", ""),
            description=skill_doc.get("description", ""),
            category=skill_doc.get("category", "other"),
            data_source=skill_doc.get("data_source", ""),
            parameters=params,
            expected_output=expected_output,
            test_input=skill_doc.get("test_input", {}),
        )

        # 构造增强反馈：原始对话摘要 + 当前代码 + 用户反馈
        enhanced_feedback = self._build_optimization_feedback(
            original_session=original_session,
            current_code=skill_doc.get("code", ""),
            user_feedback=feedback,
        )

        # 创建优化 Session
        optimize_session = self._analyzer.create_session(
            user_id=skill_doc.get("user_id", "")
        )
        optimize_session.status = SessionStatus.GENERATING
        optimize_session.rounds.append(ConversationRound(
            round_number=1,
            user_message=f"[优化] {feedback}",
            ai_message="开始优化 Skill...",
        ))
        optimize_session.spec = spec
        optimize_session.spec_confirmed = True
        await self._save_session(optimize_session)

        # 执行代码生成管线（带 feedback 和 previous_code）
        current_code = skill_doc.get("code", "")
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._controller.run(
                spec,
                initial_feedback=enhanced_feedback,
                initial_code=current_code,
            )
        )

        # 更新优化 Session
        optimize_session.status = (
            SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
        )
        optimize_session.pipeline_result = result
        await self._save_session(optimize_session)

        # 如果成功，更新 Skill
        if result.success:
            version = skill_doc.get("version", 1) + 1
            now = datetime.utcnow().isoformat()
            await self._db[SKILL_COLLECTION].update_one(
                {"tool_id": skill_id},
                {
                    "$set": {
                        "code": result.final_code,
                        "metadata": result.final_metadata,
                        "version": version,
                        "optimize_feedback": feedback,
                        "generation_rounds": result.total_rounds,
                        "generation_time": result.total_time,
                        "final_score": (
                            result.iterations[-1].eval_score.total
                            if result.iterations and result.iterations[-1].eval_score
                            else None
                        ),
                        "updated_at": now,
                    },
                    "$push": {
                        "optimize_session_ids": optimize_session.session_id,
                    },
                },
            )
            logger.info(f"✅ Skill '{skill_id}' 已优化到 v{version}")

        return {
            "status": "completed" if result.success else "failed",
            "skill_id": skill_id,
            "optimize_session_id": optimize_session.session_id,
            "success": result.success,
            "version": skill_doc.get("version", 1) + 1 if result.success else skill_doc.get("version", 1),
            "total_rounds": result.total_rounds,
            "total_time": result.total_time,
            "final_score": (
                result.iterations[-1].eval_score.total
                if result.iterations and result.iterations[-1].eval_score
                else None
            ),
            "error": result.error,
        }

    @staticmethod
    def _build_optimization_feedback(
        original_session: Optional[Dict],
        current_code: str,
        user_feedback: str,
    ) -> str:
        """构建优化反馈上下文"""
        parts = []

        # 原始需求沟通摘要
        if original_session and original_session.get("rounds"):
            parts.append("=== 原始需求沟通记录 ===")
            for r in original_session["rounds"]:
                parts.append(f"[用户]: {r.get('user_message', '')}")
                parts.append(f"[AI]: {r.get('ai_message', '')}")

        # 当前代码
        if current_code:
            parts.append(f"\n=== 当前代码（需优化）===\n```python\n{current_code}\n```")

        # 用户反馈
        parts.append(f"\n=== 用户优化需求 ===\n{user_feedback}")

        return "\n".join(parts)

    # ==================== 内部工具方法 ====================

    async def _load_session(self, session_id: str) -> Optional[SkillCreationSession]:
        """从 MongoDB 加载会话"""
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return SkillCreationSession(**doc)

    async def _save_session(self, session: SkillCreationSession) -> None:
        """保存会话到 MongoDB"""
        session.updated_at = datetime.utcnow()
        session_doc = session.model_dump(mode="json")
        await self._db[SESSION_COLLECTION].update_one(
            {"session_id": session.session_id},
            {"$set": session_doc},
            upsert=True,
        )

    async def _save_skill(
        self,
        session: SkillCreationSession,
        spec: SkillSpec,
        result: PipelineResult,
    ) -> str:
        """保存生成的 Skill 到 external_skills 集合"""
        now = datetime.utcnow().isoformat()
        skill_doc = {
            "tool_id": spec.tool_id,
            "display_name": spec.display_name,
            "description": spec.description,
            "category": spec.category,
            "data_source": spec.data_source,
            "parameters": [p.model_dump() for p in spec.parameters],
            "expected_output": spec.expected_output.model_dump(),
            "code": result.final_code,
            "metadata": result.final_metadata,
            "test_input": spec.test_input,
            "status": "active",
            "source": "generated",
            "session_id": session.session_id,
            "user_id": session.user_id,
            "generation_rounds": result.total_rounds,
            "generation_time": result.total_time,
            "final_score": (
                result.iterations[-1].eval_score.total
                if result.iterations and result.iterations[-1].eval_score
                else None
            ),
            "created_at": now,
            "updated_at": now,
        }
        await self._db[SKILL_COLLECTION].insert_one(skill_doc)
        logger.info(f"✅ Skill '{spec.tool_id}' 已保存到数据库")
        return spec.tool_id

