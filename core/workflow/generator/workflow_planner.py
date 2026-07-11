"""
工作流规划器 — LLM 驱动的对话式工作流设计

通过多轮对话理解用户需求，生成包含结构 + 缺口分析 + 提示词评估的完整蓝图。

三个核心方法：
- chat()                — 多轮对话（含方案草案 + 提示词评估 + 工具检查）
- generate_blueprint()  — 将对话转为结构化 WorkflowBlueprint JSON
- generate_optimization() — 迭代优化阶段

参考: docs/05-design/v3.0/ai-workflow-generation.md §4.2
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.llm import UnifiedLLMClient, Message
from .workflow_spec import (
    ConversationRound,
    GenerationSessionStatus,
    WorkflowBlueprint,
    WorkflowGenerationSession,
    GapAnalysisResult,
    AgentReshapingPlan,
    SkillCreationRequest,
    PlannedNode,
    PlannedEdge,
)

logger = logging.getLogger(__name__)

# ── 对话阶段 System Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT_CHAT = """\
你是一个 AI 工作流架构师，擅长根据用户需求设计多智能体协作分析流程。

## 你的任务

根据用户需求设计完整的分析工作流方案。你需要考虑三个层面：

### 层面 1：工作流结构
设计节点（Agent）和边（连接关系），确定分析流程拓扑。

### 层面 2：Agent 能力评估与提示词定制
对于每个选用的 Agent，评估其**默认提示词**是否足以应对当前流程的需求：
- ✅ 默认足够：Agent 的通用角色与本流程需求吻合，无需定制
- ⚠️ 需要定制：Agent 在本流程中的角色偏离了其默认定位，需要生成工作流专属提示词

例如：
- "标准 A 股分析流" 中的 market_analyst → 默认提示词足够 ✅
- "可转债分析流" 中的 market_analyst → 需要定制为"可转债市场分析师" ⚠️

### 层面 3：工具/Skill 缺口
检查选用的 Agent 是否有足够的工具支持，识别缺失的工具。

## 可用资源

{resource_context}

## 工作流结构规则

1. 必须有且仅有一个 start 节点和一个 end 节点
2. 所有节点必须可达（从 start 出发能到达，且能到达 end）
3. 需要并行执行的分析师应放在 parallel 和 merge 节点之间
4. 需要辩论的角色应使用 debate 节点
5. 每个 analyst/researcher/trader/risk/manager/post_processor 节点必须指定有效的 agent_id
6. agent_id 必须来自上面列出的可用 Agent
7. 节点 ID 使用小写字母+下划线，如 market_node, parallel_1
8. 节点位置按照从上到下、并行水平排列布局

## 对话规则

第一轮回复必须包含以下三部分：

📊 **方案草案** — 流程结构和步骤
📋 **提示词评估** — 哪些 Agent 用默认提示词，哪些需要定制
🔧 **工具检查** — 是否有缺失的工具需要创建

后续轮次根据用户反馈调整。不要在对话中输出 JSON。
"""

# ── 蓝图生成 System Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT_BLUEPRINT = """\
根据以下对话历史，生成完整的工作流蓝图 JSON。

## 对话历史
{conversation_history}

## 可用资源
{resource_context}

## 输出要求

请严格按照以下 JSON 格式输出（不要包含其他文本，只输出一个 JSON 对象）：

{{
    "name": "工作流名称",
    "description": "工作流描述",
    "tags": ["标签1"],
    "nodes": [
        {{"id": "start", "type": "start", "label": "开始", "position_x": 400, "position_y": 0}},
        {{"id": "xxx", "type": "analyst", "agent_id": "market_analyst", "label": "市场分析师", "position_x": 200, "position_y": 150, "description": "节点说明"}},
        {{"id": "end", "type": "end", "label": "结束", "position_x": 400, "position_y": 800}}
    ],
    "edges": [
        {{"id": "e1", "source": "start", "target": "parallel_1", "type": "normal", "condition": null}}
    ],
    "config": {{"analysis_depth": 3, "debate_rounds": "auto"}},
    "summary": "方案概述",
    "rationale": "设计思路",
    "gap_analysis": {{
        "agent_reshaping": [
            {{
                "agent_id": "market_analyst",
                "node_id": "cb_market_node",
                "original_role": "市场分析师",
                "new_role": "可转债市场分析师",
                "reshaping_direction": "从通用市场分析转向可转债专项分析，关注转股溢价率、债券价值等指标",
                "key_focus_areas": [
                    "转股溢价率趋势分析",
                    "纯债价值与转股价值对比",
                    "强赎风险监控",
                    "下修预期评估"
                ],
                "additional_tools": []
            }}
        ],
        "agents_using_default": [
            {{"agent_id": "news_analyst", "name": "新闻分析师", "reason": "新闻分析通用性强，默认提示词足够"}}
        ],
        "missing_skills": [
            {{
                "skill_name": "convertible_bond_premium_calculator",
                "skill_description": "计算可转债的转股溢价率、纯债溢价率",
                "target_agent_id": "fundamentals_analyst",
                "priority": "required"
            }}
        ],
        "available_agents": [
            {{"id": "market_analyst", "name": "市场分析师", "role_in_workflow": "可转债市场分析"}}
        ],
        "available_tools": [
            {{"id": "get_market_data", "name": "获取市场数据", "used_by_agent": "market_analyst"}}
        ],
        "analysis_summary": "4 个 Agent 需要定制提示词，3 个使用默认，需创建 1 个新 Skill"
    }}
}}

## 条件分支
当用户需求包含条件逻辑时（如"如果...则...否则..."），使用条件边：
- 边的 type 设为 "conditional"
- condition 设为 "true" 或 "false"
- 从条件节点出发的两条边分别标记 true 和 false
- 条件节点的 condition_expr 字段写判断表达式

示例：
节点：check_risk（CONDITION 类型，condition_expr: "state.get('risk_score', 0) > 80"）
边：check_risk -> deep_analysis（type: conditional, condition: "true"）
边：check_risk -> simple_decision（type: conditional, condition: "false"）

## 重要规则
1. 只输出一个 JSON 对象，不要添加 markdown 代码块标记或其他文本
2. 所有 agent_id 必须来自可用资源列表
3. 节点位置按照从上到下布局，并行节点水平分布
4. gap_analysis 中的 agent_reshaping 只包含需要定制提示词的 Agent
5. agents_using_default 包含使用默认提示词的 Agent
6. agent_reshaping 中的 reshaping_direction 只需写一句话简述定制方向，不要写完整提示词
7. key_focus_areas 列出 3-6 个关键分析维度即可
8. agent_reshaping 中每个条目必须包含 node_id，与 nodes 数组中对应节点的 id 字段保持一致
9. 同一个 agent_id 可以在多个节点出现，此时每个节点需要单独的 agent_reshaping 条目（不同 node_id，不同定制方向）
"""

# ── 优化阶段 System Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT_OPTIMIZE = """\
你是一个 AI 工作流架构师。用户已经创建了一个工作流并运行过，现在提供了反馈。
请根据反馈提出优化建议。

## 当前工作流蓝图
{blueprint_summary}

## 用户反馈
{feedback}

## 可用资源
{resource_context}

请分析问题并给出具体的优化建议，包括：
1. 结构调整（增删改节点或连接）
2. 提示词调整（哪些 Agent 需要修改提示词）
3. 工具调整（是否需要新增工具）

用自然语言描述，不要输出 JSON。
"""

MAX_DIALOGUE_ROUNDS = 10


class WorkflowPlanner:
    """
    工作流规划器

    核心调度: LLM 驱动的三阶段工作流设计
    1. 对话阶段 — 多轮沟通理解需求
    2. 蓝图阶段 — 输出结构化 JSON
    3. 优化阶段 — 根据反馈调整
    """

    def __init__(self, llm_client: Optional[UnifiedLLMClient] = None):
        self._llm_client = llm_client

    # ── 阶段 1: 对话 ────────────────────────────────────────────────

    def chat(
        self,
        session: WorkflowGenerationSession,
        user_message: str,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, str]:
        """
        处理用户消息，推进对话

        对话内容包括：
        - 工作流结构建议
        - 缺口分析（Agent 角色是否需要重塑、工具是否缺失）
        - 提示词评估（哪些 Agent 需要定制提示词）

        Args:
            session: 当前会话
            user_message: 用户消息
            resource_context: ResourceCollector 生成的资源上下文文本

        Returns:
            (更新后的会话, AI 回复消息)
        """
        if not self._llm_client:
            raise RuntimeError("LLM 客户端未初始化，请先设置 llm_client")

        # 构建消息历史
        messages = self._build_chat_messages(session, user_message, resource_context)

        # 调用 LLM
        try:
            response = self._llm_client.chat(messages)
            ai_message = response.content or "抱歉，AI 暂时无法回复，请重试。"
        except Exception as e:
            logger.error(f"[WorkflowPlanner] LLM 调用失败: {e}", exc_info=True)
            ai_message = f"AI 调用失败: {e}"

        # 更新会话
        session.current_round += 1
        session.rounds.append(ConversationRound(
            round_num=session.current_round,
            user_message=user_message,
            ai_message=ai_message,
            phase="gathering",
            timestamp=datetime.utcnow(),
        ))
        session.updated_at = datetime.utcnow()

        return session, ai_message

    def _build_chat_messages(
        self,
        session: WorkflowGenerationSession,
        user_message: str,
        resource_context: str,
    ) -> List[Message]:
        """构建对话阶段的 LLM 消息列表"""
        messages: List[Message] = []

        # System prompt（包含资源上下文）
        system_content = SYSTEM_PROMPT_CHAT.format(resource_context=resource_context)
        messages.append(Message(role="system", content=system_content))

        # 历史对话
        for r in session.rounds:
            if r.user_message:
                messages.append(Message(role="user", content=r.user_message))
            if r.ai_message:
                messages.append(Message(role="assistant", content=r.ai_message))

        # 当前用户消息
        messages.append(Message(role="user", content=user_message))

        return messages

    # ── 阶段 2: 蓝图生成 ────────────────────────────────────────────

    def generate_blueprint(
        self,
        session: WorkflowGenerationSession,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, Optional[WorkflowBlueprint]]:
        """
        根据对话历史生成完整的 WorkflowBlueprint（含缺口分析 + 提示词评估）

        在用户确认方案后调用，要求 LLM 输出结构化 JSON。

        Args:
            session: 当前会话（应包含至少 1 轮对话）
            resource_context: 资源上下文

        Returns:
            (更新后的会话, WorkflowBlueprint 或 None)
        """
        if not self._llm_client:
            raise RuntimeError("LLM 客户端未初始化，请先设置 llm_client")

        session.status = GenerationSessionStatus.PLANNING
        session.updated_at = datetime.utcnow()

        # 拼接对话历史
        conversation_history = self._format_conversation_history(session)

        # 构建蓝图生成 prompt
        system_content = SYSTEM_PROMPT_BLUEPRINT.format(
            conversation_history=conversation_history,
            resource_context=resource_context,
        )
        messages = [
            Message(role="system", content=system_content),
            Message(role="user", content="请根据上述对话历史生成完整的工作流蓝图 JSON。"),
        ]

        try:
            response = self._llm_client.chat(messages)
            raw_content = response.content or ""
            blueprint = self._parse_blueprint_json(raw_content)
            if blueprint:
                session.blueprint = blueprint
                session.status = GenerationSessionStatus.BLUEPRINT_READY
                logger.info(
                    f"[WorkflowPlanner] 蓝图生成成功: {blueprint.name}, "
                    f"节点={len(blueprint.nodes)}, 边={len(blueprint.edges)}"
                )
            else:
                session.status = GenerationSessionStatus.GATHERING
                session.error = "蓝图 JSON 解析失败，请继续对话完善需求"
                logger.warning("[WorkflowPlanner] 蓝图 JSON 解析失败")
        except Exception as e:
            logger.error(f"[WorkflowPlanner] 蓝图生成失败: {e}", exc_info=True)
            session.status = GenerationSessionStatus.GATHERING
            session.error = f"蓝图生成失败: {e}"

        session.updated_at = datetime.utcnow()
        return session, session.blueprint

    def _format_conversation_history(self, session: WorkflowGenerationSession) -> str:
        """将会话历史格式化为文本"""
        lines = []
        for r in session.rounds:
            lines.append(f"用户: {r.user_message}")
            lines.append(f"AI: {r.ai_message}")
            lines.append("")
        return "\n".join(lines)

    def _parse_blueprint_json(self, raw: str) -> Optional[WorkflowBlueprint]:
        """
        从 LLM 输出中提取并解析蓝图 JSON

        尝试多种策略提取 JSON：
        1. 直接解析整段文本
        2. 提取 ```json ... ``` 代码块
        3. 提取第一个 { ... } 对象
        """
        json_str = raw.strip()

        # 策略 1: 直接解析
        data = self._try_parse_json(json_str)

        # 策略 2: 提取 markdown 代码块
        if data is None:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", json_str, re.DOTALL)
            if match:
                data = self._try_parse_json(match.group(1).strip())

        # 策略 3: 提取第一个完整 JSON 对象
        if data is None:
            brace_start = json_str.find("{")
            if brace_start >= 0:
                # 找到最后一个匹配的 }
                depth = 0
                for i in range(brace_start, len(json_str)):
                    if json_str[i] == "{":
                        depth += 1
                    elif json_str[i] == "}":
                        depth -= 1
                        if depth == 0:
                            data = self._try_parse_json(json_str[brace_start:i + 1])
                            break

        if data is None:
            logger.warning("[WorkflowPlanner] 无法从 LLM 输出中提取 JSON")
            return None

        return self._build_blueprint_from_dict(data)


    @staticmethod
    def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """尝试解析 JSON，失败返回 None"""
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _build_blueprint_from_dict(self, data: Dict[str, Any]) -> Optional[WorkflowBlueprint]:
        """将解析后的 dict 转换为 WorkflowBlueprint 对象"""
        try:
            # 解析节点
            nodes = []
            for nd in data.get("nodes", []):
                nodes.append(PlannedNode(
                    id=nd.get("id", ""),
                    type=nd.get("type", ""),
                    agent_id=nd.get("agent_id"),
                    label=nd.get("label", ""),
                    position_x=nd.get("position_x", 0),
                    position_y=nd.get("position_y", 0),
                    config=nd.get("config", {}),
                    description=nd.get("description", ""),
                ))

            # 解析边
            edges = []
            for ed in data.get("edges", []):
                edges.append(PlannedEdge(
                    id=ed.get("id", ""),
                    source=ed.get("source", ""),
                    target=ed.get("target", ""),
                    label=ed.get("label"),
                    animated=ed.get("animated", False),
                ))

            # 解析缺口分析
            gap_data = data.get("gap_analysis")
            gap_analysis = None
            if gap_data and isinstance(gap_data, dict):
                reshaping_fields = set(AgentReshapingPlan.__fields__.keys())
                skill_fields = set(SkillCreationRequest.__fields__.keys())
                reshaping = [
                    AgentReshapingPlan(**{k: v for k, v in r.items() if k in reshaping_fields})
                    for r in gap_data.get("agent_reshaping", [])
                ]
                missing_skills = [
                    SkillCreationRequest(**{k: v for k, v in s.items() if k in skill_fields})
                    for s in gap_data.get("missing_skills", [])
                ]
                gap_analysis = GapAnalysisResult(
                    agent_reshaping=reshaping,
                    agents_using_default=gap_data.get("agents_using_default", []),
                    missing_skills=missing_skills,
                    available_agents=gap_data.get("available_agents", []),
                    available_tools=gap_data.get("available_tools", []),
                    analysis_summary=gap_data.get("analysis_summary", ""),
                )

            blueprint = WorkflowBlueprint(
                name=data.get("name", ""),
                description=data.get("description", ""),
                tags=data.get("tags", []),
                nodes=nodes,
                edges=edges,
                config=data.get("config", {}),
                summary=data.get("summary", ""),
                rationale=data.get("rationale", ""),
                gap_analysis=gap_analysis,
            )

            # 计算创建进度
            if gap_analysis:
                blueprint.creation_progress = {
                    "skills_total": len(gap_analysis.missing_skills),
                    "skills_completed": 0,
                    "prompts_total": len(gap_analysis.agent_reshaping),
                    "prompts_completed": 0,
                    "workflow_created": False,
                }

            return blueprint

        except Exception as e:
            logger.error(f"[WorkflowPlanner] 蓝图结构解析失败: {e}", exc_info=True)
            return None

    # ── 阶段 3: 迭代优化 ────────────────────────────────────────────

    def generate_optimization(
        self,
        session: WorkflowGenerationSession,
        feedback: str,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, str]:
        """
        根据用户反馈生成优化建议

        Args:
            session: 当前会话（应已有 blueprint 和 workflow_id）
            feedback: 用户对运行结果的反馈
            resource_context: 资源上下文

        Returns:
            (更新后的会话, AI 优化建议)
        """
        if not self._llm_client:
            raise RuntimeError("LLM 客户端未初始化，请先设置 llm_client")

        # 构建蓝图摘要
        blueprint_summary = self._format_blueprint_summary(session.blueprint)

        # 构建消息
        system_content = SYSTEM_PROMPT_OPTIMIZE.format(
            blueprint_summary=blueprint_summary,
            feedback=feedback,
            resource_context=resource_context,
        )

        # 包含优化对话历史
        messages: List[Message] = [Message(role="system", content=system_content)]
        for r in session.optimize_rounds:
            if r.user_message:
                messages.append(Message(role="user", content=r.user_message))
            if r.ai_message:
                messages.append(Message(role="assistant", content=r.ai_message))
        messages.append(Message(role="user", content=feedback))

        try:
            response = self._llm_client.chat(messages)
            ai_message = response.content or "抱歉，AI 暂时无法回复，请重试。"
        except Exception as e:
            logger.error(f"[WorkflowPlanner] 优化建议生成失败: {e}", exc_info=True)
            ai_message = f"AI 调用失败: {e}"

        # 更新会话
        session.optimize_count += 1
        session.optimize_rounds.append(ConversationRound(
            round_num=session.optimize_count,
            user_message=feedback,
            ai_message=ai_message,
            phase="optimizing",
            timestamp=datetime.utcnow(),
        ))
        session.status = GenerationSessionStatus.OPTIMIZING
        session.updated_at = datetime.utcnow()

        return session, ai_message

    @staticmethod
    def _format_blueprint_summary(blueprint: Optional[WorkflowBlueprint]) -> str:
        """将蓝图格式化为摘要文本"""
        if not blueprint:
            return "(无蓝图信息)"

        lines = [
            f"**名称**: {blueprint.name}",
            f"**描述**: {blueprint.description}",
            f"**节点**: {len(blueprint.nodes)} 个",
        ]

        for n in blueprint.nodes:
            agent_info = f" ({n.agent_id})" if n.agent_id else ""
            lines.append(f"  - {n.id}: {n.label}{agent_info} [{n.type}]")

        lines.append(f"**边**: {len(blueprint.edges)} 条")
        for e in blueprint.edges:
            lines.append(f"  - {e.source} → {e.target}")

        if blueprint.gap_analysis:
            ga = blueprint.gap_analysis
            if ga.agent_reshaping:
                lines.append(f"**提示词定制**: {len(ga.agent_reshaping)} 个 Agent")
            if ga.agents_using_default:
                lines.append(f"**使用默认提示词**: {len(ga.agents_using_default)} 个 Agent")
            if ga.missing_skills:
                lines.append(f"**缺失工具**: {len(ga.missing_skills)} 个")

        return "\n".join(lines)