"""
需求分析器 — 多轮对话式需求沟通

核心能力：
1. 清晰度评估 — 判断用户需求的明确程度 (HIGH/MEDIUM/LOW)
2. 边界检测 — 检查需求是否超出单个 Skill 的范围
3. 多轮对话 — 1-3 轮渐进式需求确认
4. 规格生成 — 将确认的需求转化为结构化 SkillSpec
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.llm import UnifiedLLMClient, Message

from .skill_spec import (
    BoundaryCheck,
    ClarityLevel,
    ConversationRound,
    SessionStatus,
    SkillCreationSession,
    SkillSpec,
)

logger = logging.getLogger(__name__)


class RequirementAnalyzer:
    """
    需求分析器

    通过多轮对话将用户的自然语言需求转化为结构化 SkillSpec。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        self._client = llm_client
        self._provider = provider
        self._model = model

    def _get_client(self) -> UnifiedLLMClient:
        """懒加载 LLM 客户端"""
        if self._client is None:
            kwargs = {}
            if self._model:
                kwargs["model"] = self._model
            self._client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        return self._client

    # ==================== 会话管理 ====================

    def create_session(self, user_id: str = "") -> SkillCreationSession:
        """创建新的 Skill 创建会话"""
        return SkillCreationSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            status=SessionStatus.GATHERING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def process_user_input(
        self,
        session: SkillCreationSession,
        user_message: str,
    ) -> Tuple[SkillCreationSession, str]:
        """
        处理用户输入，推进对话

        Args:
            session: 当前会话
            user_message: 用户消息

        Returns:
            (更新后的会话, AI 回复消息)
        """
        session.updated_at = datetime.utcnow()

        # 如果是第一轮，先做清晰度评估和边界检测
        if session.current_round == 0:
            clarity = self._assess_clarity(user_message)
            session.clarity_level = clarity

            boundary = self._check_boundary(user_message)
            session.boundary_check = boundary

            # 如果超出边界，返回拆分建议
            if not boundary.within_boundary:
                ai_msg = self._build_boundary_warning(boundary)
                round_obj = ConversationRound(
                    round_number=1,
                    ai_message=ai_msg,
                    user_message=user_message,
                )
                session.rounds.append(round_obj)
                session.current_round = 1
                return session, ai_msg

        # 推进对话
        session.current_round += 1
        max_rounds = self._get_max_rounds(session.clarity_level)

        # 第 2 轮及以后：根据用户最新反馈重新评估边界，复杂度提醒会随之更新
        if session.current_round >= 2:
            conversation = self._collect_conversation(session, user_message)
            boundary = self._check_boundary(user_message, conversation_context=conversation)
            session.boundary_check = boundary

        if session.current_round >= max_rounds:
            # 最后一轮：生成规格确认
            ai_msg = self._build_spec_confirmation(session, user_message)
        elif session.current_round == 1:
            # 第 1 轮：初步理解 + 功能点拆解
            ai_msg = self._build_round1_response(user_message)
        else:
            # 第 2 轮：技术细化
            ai_msg = self._build_round2_response(session, user_message)

        round_obj = ConversationRound(
            round_number=session.current_round,
            ai_message=ai_msg,
            user_message=user_message,
        )
        session.rounds.append(round_obj)

        return session, ai_msg

    def confirm_spec(
        self, session: SkillCreationSession, user_message: str
    ) -> Tuple[SkillCreationSession, Optional[SkillSpec]]:
        """
        用户确认规格后，生成 SkillSpec

        Args:
            session: 当前会话
            user_message: 用户的确认消息（"确认" / 补充修改）

        Returns:
            (更新后的会话, 生成的 SkillSpec 或 None)
        """
        # 收集所有对话内容
        conversation = self._collect_conversation(session, user_message)

        # LLM 生成结构化 SkillSpec
        spec = self._generate_spec(conversation)

        if spec:
            session.spec = spec
            session.spec_confirmed = True
            session.status = SessionStatus.CONFIRMED
            session.updated_at = datetime.utcnow()

        return session, spec

    # ==================== 清晰度评估 ====================

    def _assess_clarity(self, user_message: str) -> ClarityLevel:
        """评估需求清晰度"""
        client = self._get_client()
        prompt = (
            "请评估以下用户需求的清晰度（1-5分）。\n"
            "5分=非常清晰（明确了数据源、参数、输出），"
            "3分=一般（有主题但缺细节），"
            "1分=模糊（只有大方向）。\n\n"
            f"用户需求: {user_message}\n\n"
            "只回复一个数字（1-5），不要其他内容。"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            score_text = (response.content or "3").strip()
            score = int(re.search(r"[1-5]", score_text).group())
        except Exception:
            score = 3

        if score >= 4:
            return ClarityLevel.HIGH
        elif score >= 3:
            return ClarityLevel.MEDIUM
        else:
            return ClarityLevel.LOW

    # ==================== 边界检测 ====================

    def _check_boundary(
        self, user_message: str, conversation_context: Optional[str] = None
    ) -> BoundaryCheck:
        """检测需求是否超出单个 Skill 范围。若有对话历史，基于最新共识重新评估。"""
        client = self._get_client()
        if conversation_context:
            prompt = (
                "你是 Skill 边界检测专家。一个 Skill 应该只做一件事：从一个数据源获取数据并返回。\n\n"
                "**重要**：用户经过多轮对话后，需求可能已显著调整，例如：\n"
                "- 选择了某个子方案（如「方案A/B/C」）\n"
                "- 改为通过 API 获取（而非 PDF 解析）\n"
                "- 缩小了范围或简化了实现方式\n\n"
                "你必须基于**用户最新一轮的明确选择**重新评估，而非沿用首轮的判断。"
                "若用户已选择通过 API、或选择了较简单的子方案，则复杂度应降低，concerns 和 decomposition_suggestions 需相应更新。\n\n"
                f"对话历史:\n{conversation_context}\n\n"
                "请用 JSON 回复（不要其他内容）：\n"
                '{"within_boundary": true/false, "complexity_score": 1-5, '
                '"concerns": ["问题1", ...], "decomposition_suggestions": ["建议1", ...]}'
            )
        else:
            prompt = (
                "你是 Skill 边界检测专家。一个 Skill 应该只做一件事：从一个数据源获取数据并返回。\n"
                "以下需求是否超出了单个 Skill 的范围？\n\n"
                f"需求: {user_message}\n\n"
                "请用 JSON 回复（不要其他内容）：\n"
                '{"within_boundary": true/false, "complexity_score": 1-5, '
                '"concerns": ["问题1", ...], "decomposition_suggestions": ["建议1", ...]}'
            )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            raw = response.content or "{}"
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return BoundaryCheck(**data)
        except Exception as e:
            logger.warning(f"边界检测失败: {e}")

        return BoundaryCheck()

    # ==================== 对话构建 ====================

    @staticmethod
    def _get_max_rounds(clarity: Optional[ClarityLevel]) -> int:
        """根据清晰度决定对话轮数"""
        if clarity == ClarityLevel.HIGH:
            return 1
        elif clarity == ClarityLevel.MEDIUM:
            return 2
        return 3

    def _build_round1_response(self, user_message: str) -> str:
        """第 1 轮：初步理解 + 功能点拆解 + 数据源引导"""
        client = self._get_client()
        prompt = (
            "你是 Skill 需求分析专家，不仅理解用户需求，更要主动给出专业建议。\n\n"
            "## 项目背景\n"
            "你所在的是 **TradingAgents-CN**：面向中文用户的多智能体股票分析学习平台。"
            "平台专注 A股/港股/美股 的合规研究与策略实验，使用 AI Agent 调用各类数据获取工具（Skill）进行分析。"
            "用户正在创建的 Skill 将作为 Agent 可调用的数据获取工具，用于获取行情、财报、新闻、资金流等金融数据。\n\n"
            "## 你的任务\n"
            "1. 复述你的理解\n"
            "2. 用表格列出功能点（目标市场、数据源、输入参数、返回字段、调用方式）\n"
            "3. **主动建议**：根据用户需求给出专业建议（如更合适的实现方式、常见坑、最佳实践）\n"
            "4. **数据源引导（重要）**：\n"
            "   - 先问用户：您是否有偏好的数据源？\n"
            "   - 若用户说「不确定」「不知道」「没有」「都可以」："
            "结合你对 A股/中国金融数据生态的了解，根据用户需求类型（财报、新闻、行情、资金流等），"
            "推荐 2-3 个合适的数据源，简要说明各自特点和适用场景，让用户选择。\n"
            "   - 不要只说「需通过参数传入数据源」而不给建议，这样用户会不知道如何操作。\n\n"
            "5. 提出其他需要确认的问题\n\n"
            f"用户描述: {user_message}"
        )
        response = client.chat([Message(role="user", content=prompt)])
        return response.content or "请补充更多需求细节。"

    def _build_round2_response(
        self, session: SkillCreationSession, user_message: str
    ) -> str:
        """第 2 轮：技术细化"""
        history = self._collect_conversation(session, user_message)
        client = self._get_client()
        prompt = (
            "你是 Skill 需求分析专家，所在项目是 **TradingAgents-CN**（A股/港股/美股多智能体股票分析平台）。"
            "正在进行第 2 轮技术细化。\n\n"
            "请根据之前的对话和用户新的反馈：\n"
            "1. 确认技术方案（数据接口、返回格式）\n"
            "2. **主动建议**：根据用户需求给出技术方案建议（如推荐实现方式、边界情况处理）\n"
            "3. **若数据源仍未明确**：结合你对 A股/中国金融数据生态的了解，"
            "根据需求类型给出 2-3 个具体数据源推荐及理由，让用户选择\n"
            "4. 给出推荐方案让用户选择（而不是问开放性问题）\n"
            "5. 列出最终的参数和返回字段清单\n\n"
            f"对话历史:\n{history}"
        )
        response = client.chat([Message(role="user", content=prompt)])
        return response.content or "请确认技术方案。"

    def _build_spec_confirmation(
        self, session: SkillCreationSession, user_message: str
    ) -> str:
        """最后一轮：生成规格确认摘要"""
        history = self._collect_conversation(session, user_message)
        client = self._get_client()
        prompt = (
            "你是 Skill 需求分析专家，请根据所有对话内容生成最终的规格确认摘要。\n"
            "用以下格式输出：\n"
            "## Skill 规格确认\n"
            "- **tool_id**: xxx\n"
            "- **名称**: xxx\n"
            "- **描述**: xxx\n"
            "- **分类**: xxx\n"
            "- **数据源**: xxx\n"
            "- **参数**: 列表\n"
            "- **返回字段**: 列表\n"
            "- **约束**: 列表\n\n"
            "最后问用户: '以上规格是否正确？确认后将开始生成代码。'\n\n"
            f"对话历史:\n{history}"
        )
        response = client.chat([Message(role="user", content=prompt)])
        return response.content or "请确认以上规格。"

    @staticmethod
    def _build_boundary_warning(check: BoundaryCheck) -> str:
        """构建边界警告消息"""
        concerns = "\n".join(f"  - {c}" for c in check.concerns)
        suggestions = "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(check.decomposition_suggestions)
        )
        return (
            "⚠️ 你的需求包含了多个功能层级，建议拆分：\n\n"
            f"**关注点：**\n{concerns}\n\n"
            f"**建议拆分为：**\n{suggestions}\n\n"
            "每个 Skill 只做一件事（获取一类数据），分析和决策由 Agent/Workflow 完成。\n"
            "请选择一个 Skill 开始创建，或者告诉我你想要的是哪个功能。"
        )

    # ==================== 对话收集 & 规格生成 ====================

    @staticmethod
    def _collect_conversation(
        session: SkillCreationSession, current_message: str = ""
    ) -> str:
        """收集所有对话历史为格式化字符串"""
        parts = []
        for r in session.rounds:
            parts.append(f"[用户 - 第{r.round_number}轮]: {r.user_message}")
            parts.append(f"[AI - 第{r.round_number}轮]: {r.ai_message}")
        if current_message:
            parts.append(f"[用户 - 最新]: {current_message}")
        return "\n\n".join(parts)

    def _generate_spec(self, conversation: str) -> Optional[SkillSpec]:
        """通过 LLM 将对话转化为结构化 SkillSpec"""
        client = self._get_client()
        prompt = (
            "你是 Skill 规格生成器。请根据以下对话内容，"
            "提取出一个结构化的 Skill 规格（JSON 格式）。\n\n"
            "**重要**：\n"
            "1. 若对话中有「[用户 - 最新]」或用户明确选择方案（如选 A/B/C），必须严格按用户选择生成，不可忽略。\n"
            "2. data_source 填写对话中确定的具体数据源标识；用户已选择则用其选择，否则用 AI 推荐的主数据源。\n"
            "3. 不要写「需通过参数传入」等模糊描述。\n\n"
            f"对话内容:\n{conversation}\n\n"
            "请严格用以下 JSON 格式输出（不要其他内容）：\n"
            "{\n"
            '  "tool_id": "snake_case_id",\n'
            '  "display_name": "中文显示名称",\n'
            '  "description": "功能描述",\n'
            '  "category": "news|market|fundamentals|social|technical|utility",\n'
            '  "data_source": "对话中确定的数据源标识",\n'
            '  "parameters": [\n'
            '    {"name": "param1", "type": "string", "description": "说明", '
            '"required": true}\n'
            "  ],\n"
            '  "expected_output": {\n'
            '    "type": "list[dict]",\n'
            '    "fields": ["field1", "field2"],\n'
            '    "description": "输出描述"\n'
            "  },\n"
            '  "constraints": ["约束1"],\n'
            '  "test_input": {"param1": "测试值"}\n'
            "}"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            raw = response.content or ""
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return SkillSpec(**data)
        except Exception as e:
            logger.error(f"SkillSpec 生成失败: {e}")
        return None
