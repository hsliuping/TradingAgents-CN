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

## ⚠️ 关键约束：Agent 选择规则（严格遵守）

1. **只能从下方「可用资源」中列出的 Agent 中选择**，禁止编造、联想或杜撰不存在的 agent_id
2. **仔细阅读每个 Agent 的 description**，找到能力最匹配的。例如：
   - 需要估值分析 → 用 `valuation_analyst_v2`，不要编造 `buffett_valuation_analyst`
   - 需要护城河/竞争优势分析 → 用 `fundamentals_analyst_v2`（基本面分析涵盖竞争优势/护城河），不要编造 `moat_analyst`
   - 需要管理层评估 → 同样用 `fundamentals_analyst_v2`（基本面分析涵盖管理层评估），不要编造 `management_analyst`
3. **如果确实没有合适的 Agent 能满足用户需求，在回复中明确告知用户**，而非编造一个听起来合理的名称
4. **Agent 名称只是标签**，真正的分析方向通过提示词定制（层面 2）来实现，不需要为每个细分方向新建 Agent
5. **agent_id 必须逐字精确复制**，包括 `_v2`、`_v1` 等后缀。例如 `fundamentals_analyst_v2` 不能写成 `fundamentals_analyst`，`valuation_analyst_v2` 不能写成 `valuation_analyst`

## 可用资源

{resource_context}

## 工作流结构规则

1. 必须有且仅有一个 start 节点和一个 end 节点
2. 所有节点必须可达（从 start 出发能到达，且能到达 end）
3. 需要并行执行的分析师应放在 parallel 和 merge 节点之间
4. 需要辩论的角色应使用 debate 节点
5. 每个 analyst/researcher/trader/risk/manager/post_processor 节点必须指定有效的 agent_id
6. agent_id 必须严格来自上面「可用资源」中列出的 Agent ID（直接复制，不要改动）
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
    "input_config": {{
        "fields": [
            {{
                "name": "ticker",
                "label": "股票代码",
                "type": "string",
                "required": true,
                "default": null,
                "description": "要分析的股票代码，如 600519.SH",
                "placeholder": "如: 600519.SH",
                "options": null,
                "option_labels": null,
                "min": null,
                "max": null,
                "group": "基本参数",
                "order": 1
            }},
            {{
                "name": "research_depth",
                "label": "分析深度",
                "type": "select",
                "required": false,
                "default": "标准",
                "description": "分析深度等级",
                "placeholder": "",
                "options": ["快速", "基础", "标准", "深度", "全面"],
                "option_labels": ["快速 (2-4分钟)", "基础 (4-6分钟)", "标准 (6-10分钟)", "深度 (10-15分钟)", "全面 (15-25分钟)"],
                "min": null,
                "max": null,
                "group": "基本参数",
                "order": 2
            }}
        ]
    }},
    "summary": "方案概述",
    "rationale": "设计思路",
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
            "additional_tools": [
                "convertible_bond_data_fetcher",
                "premium_rate_calculator"
            ]
        }}
    ],
    "agents_using_default": [
        {{"agent_id": "news_analyst", "name": "新闻分析师", "reason": "新闻分析通用性强，默认提示词足够"}}
    ],
    "analysis_summary": "4 个 Agent 需要定制提示词，3 个使用默认"
}}

## input_config 字段说明
input_config.fields 定义工作流执行时需要的输入参数，前端会根据这些定义自动生成表单：
- name: 参数名（传给后端的 key，如 ticker / analysis_date / analysis_target）
- label: 表单显示标签
- type: 控件类型，可选值：string（单行文本）/ textarea（多行文本）/ number（数字）/ boolean（开关）/ date（日期）/ select（下拉单选）/ multiselect（下拉多选）
- required: 是否必填
- default: 默认值（null 表示无默认值）
- description: 参数描述/提示
- placeholder: 输入框占位提示
- options: 选项列表（仅 select/multiselect 时使用，其他类型填 null）
- option_labels: 选项显示名（与 options 一一对应，让用户看到更友好的选项名）
- min/max: 数值范围（仅 number 类型使用，其他类型填 null）
- group: 分组标签（如"基本参数"/"高级参数"，同组的参数会显示在一起）
- order: 排序序号（数字越小越靠前）

不同工作流类型的 input_config 示例：
- 股票分析：ticker(string,必填) / analysis_date(date) / research_depth(select) / quick_analysis_model(string) / deep_analysis_model(string)
- 通用研究：analysis_target(textarea,必填) / research_depth(select) / quick_analysis_model(select) / deep_analysis_model(select) + 该流程特需的自定义参数
- ETF分析：ticker(string,必填) / analysis_date(date) / research_depth(select)
- 持仓分析：portfolio_data(textarea,必填) / analysis_date(date)

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
2. 所有 agent_id 必须逐字精确复制可用资源列表中的 ID，包括 `_v2`/`_v1` 等后缀，禁止缩写或省略
3. 节点位置按照从上到下布局，并行节点水平分布
4. agent_reshaping 只包含需要定制提示词的 Agent
5. agents_using_default 包含使用默认提示词的 Agent
6. agent_reshaping 中的 reshaping_direction 只需写一句话简述定制方向，不要写完整提示词
7. key_focus_areas 列出 3-6 个关键分析维度即可
8. agent_reshaping 中每个条目必须包含 node_id，与 nodes 数组中对应节点的 id 字段保持一致
9. 同一个 agent_id 可以在多个节点出现，此时每个节点需要单独的 agent_reshaping 条目（不同 node_id，不同定制方向）
10. 不需要填写 available_agents / available_tools / missing_skills，系统会自动完成工具匹配
11. agent_reshaping 中的 additional_tools 字段（可选）：当该 Agent 的分析任务需要专用工具、且可用资源中没有对应工具时，列出这些工具名（snake_case 命名）。如果可用资源中的工具已足够覆盖分析需求，则省略此字段
12. input_config.fields 必须列出该工作流执行时需要的所有输入参数，每个参数的 name 要与后端代码中使用的字段名一致（如 ticker / analysis_date / analysis_target）
13. 对于通用研究流程（workflow_type=general），至少要包含 analysis_target（textarea, 必填）参数
14. 对于股票分析流程，至少要包含 ticker（string, 必填）参数
15. input_config.fields 可以为空数组（表示无需额外输入参数）"""

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
        # 结构化的可用 Agent 列表（id/name/description/category/source），
        # 由 ResourceCollector.collect_all() 提供，用于蓝图阶段的白名单校验。
        self._available_agents: List[Dict[str, Any]] = []
        # 🛡️ 重试计数器：记录蓝图生成时因 agent_id 幻觉触发重试的总次数（用于监控 LLM 质量）
        self._hallucination_retry_count: int = 0

    def set_available_agents(self, agents: List[Dict[str, Any]]) -> None:
        """
        注入结构化可用 Agent 列表（用于后置白名单校验）

        由 workflow_generation_service 在调用 chat/generate_blueprint 之前注入。
        """
        self._available_agents = list(agents or [])

    @property
    def available_agent_ids(self) -> set:
        """合法的 agent_id 集合（白名单）"""
        return {a.get("id") for a in self._available_agents if a.get("id")}

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

        # 🔍 调试：打印当前可用的 Agent 白名单
        whitelist_ids = sorted(self.available_agent_ids)
        logger.info(
            f"📋 [WorkflowPlanner.chat] 白名单 Agent ({len(whitelist_ids)} 个): "
            f"{whitelist_ids}"
        )

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

        # 🔍 调试：检查 LLM 回复中是否包含不在白名单中的 agent_id
        mentioned_ids = set(re.findall(r'\b([a-z_]+_v[12]|[a-z_]+_analyst|[a-z_]+_assistant[a-z0-9_]*)\b', ai_message))
        whitelist_set = self.available_agent_ids
        hallucinated_in_chat = mentioned_ids - whitelist_set
        if hallucinated_in_chat:
            logger.warning(
                f"⚠️ [WorkflowPlanner.chat] LLM 回复中提到了不在白名单中的 agent_id: "
                f"{sorted(hallucinated_in_chat)}"
            )

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

        # 🔍 调试：打印蓝图生成时的 Agent 白名单
        whitelist_ids = sorted(self.available_agent_ids)
        logger.info(
            f"📋 [WorkflowPlanner.generate_blueprint] 白名单 Agent ({len(whitelist_ids)} 个): "
            f"{whitelist_ids}"
        )

        # 拼接对话历史
        conversation_history = self._format_conversation_history(session)

        # 第 1 次生成
        blueprint = self._call_llm_for_blueprint(conversation_history, resource_context, None)

        # 🛡️ 如果检测到 agent_id 幻觉，注入建议后重试 1 次
        if (
            blueprint is not None
            and self._available_agents
            and blueprint._invalid_agent_ids
        ):
            invalid_map = dict(blueprint._invalid_agent_ids)
            retry_hint = self._build_retry_hint(invalid_map)
            self._hallucination_retry_count += 1
            logger.info(
                f"🔁 [WorkflowPlanner] 检测到 {len(invalid_map)} 个幻觉 agent_id，"
                f"已自动建议合法替换，重试 1 次（累计重试: {self._hallucination_retry_count}）"
            )
            retry_bp = self._call_llm_for_blueprint(
                conversation_history, resource_context, retry_hint
            )
            if retry_bp is not None:
                blueprint = retry_bp

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

        session.updated_at = datetime.utcnow()
        return session, session.blueprint

    def _call_llm_for_blueprint(
        self,
        conversation_history: str,
        resource_context: str,
        retry_hint: Optional[str],
    ) -> Optional[WorkflowBlueprint]:
        """调用 LLM 生成蓝图并解析，可选追加重试提示"""
        system_content = SYSTEM_PROMPT_BLUEPRINT.format(
            conversation_history=conversation_history,
            resource_context=resource_context,
        )
        messages: List[Message] = [Message(role="system", content=system_content)]
        if retry_hint:
            messages.append(Message(
                role="user",
                content=(
                    "上一轮生成的蓝图中包含不存在的 agent_id，请用下方建议的合法 ID 替换后重新输出完整 JSON。\n"
                    f"{retry_hint}\n\n"
                    "请输出完整的工作流蓝图 JSON。"
                ),
            ))
        else:
            messages.append(Message(role="user", content="请根据上述对话历史生成完整的工作流蓝图 JSON。"))

        try:
            response = self._llm_client.chat(messages)
            raw_content = response.content or ""
            logger.debug(f"[WorkflowPlanner] LLM 原始返回内容（长度={len(raw_content)}）")
            return self._parse_blueprint_json(raw_content)
        except Exception as e:
            logger.error(f"[WorkflowPlanner] LLM 调用失败: {e}", exc_info=True)
            return None

    def _build_retry_hint(self, invalid_map: Dict[str, str]) -> str:
        """构造重试提示：列出非法 ID → 建议合法 ID 的映射"""
        lines = ["## ⚠️ 必须修正的 agent_id 幻觉"]
        for bad, good in invalid_map.items():
            if good:
                lines.append(f"- ❌ `{bad}` 不存在 → ✅ 请改为 `{good}`")
            else:
                lines.append(
                    f"- ❌ `{bad}` 不存在 → 列表里没有完全等价的 Agent，请从【可用 Agent】中挑选最接近的"
                )
        # 强调"必须从上面列表里挑"
        lines.append("")
        lines.append(
            "**重要**：agent_id 必须严格使用上文【可用的 Agent（智能体）】中列出的 ID，"
            "禁止编造或联想任何不在列表中的 ID。"
        )
        return "\n".join(lines)

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
            logger.warning(f"[WorkflowPlanner] 无法从 LLM 输出中提取 JSON，长度={len(json_str)}")
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

            # 解析缺口分析（LLM 提供 agent_reshaping + agents_using_default，
            # available_tools / missing_skills 由后续 CapabilityIndex 搜索填充）
            gap_data = data.get("gap_analysis")
            agent_reshaping_raw = data.get("agent_reshaping", [])
            agents_using_default_raw = data.get("agents_using_default", [])
            analysis_summary = data.get("analysis_summary", "")

            # 兼容旧格式：如果还有 gap_analysis 嵌套，从中提取
            if gap_data and isinstance(gap_data, dict):
                if not agent_reshaping_raw:
                    agent_reshaping_raw = gap_data.get("agent_reshaping", [])
                if not agents_using_default_raw:
                    agents_using_default_raw = gap_data.get("agents_using_default", [])
                if not analysis_summary:
                    analysis_summary = gap_data.get("analysis_summary", "")

            reshaping_fields = set(AgentReshapingPlan.__fields__.keys())
            reshaping = [
                AgentReshapingPlan(**{k: v for k, v in r.items() if k in reshaping_fields})
                for r in agent_reshaping_raw
            ]

            gap_analysis = GapAnalysisResult(
                agent_reshaping=reshaping,
                agents_using_default=agents_using_default_raw,
                missing_skills=[],  # 由 CapabilityIndex 搜索填充
                available_agents=[],  # 由 CapabilityIndex 搜索填充
                available_tools=[],  # 由 CapabilityIndex 搜索填充
                analysis_summary=analysis_summary,
            )

            blueprint = WorkflowBlueprint(
                name=data.get("name", ""),
                description=data.get("description", ""),
                tags=data.get("tags", []),
                nodes=nodes,
                edges=edges,
                config=data.get("config", {}),
                input_config=data.get("input_config") or {"fields": []},
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

            # 🛡️ 防幻觉：agent_id 白名单校验（参考 Agent 工坊 gap_analysis 的做法）
            if self._available_agents:
                self._enforce_agent_whitelist(blueprint)

            return blueprint

        except Exception as e:
            logger.error(f"[WorkflowPlanner] 蓝图结构解析失败: {e}", exc_info=True)
            return None

    # ── 阶段 2.5: 防幻觉白名单校验 ────────────────────────────────

    def _enforce_agent_whitelist(self, blueprint: WorkflowBlueprint) -> None:
        """
        对蓝图中的 agent_id 做白名单校验，参考 Agent 工坊 gap_analysis 防幻觉逻辑。

        校验范围：
        - nodes[].agent_id      — 运行时执行节点，幻觉会导致运行时崩溃
        - agent_reshaping[].agent_id — 提示词生成目标，幻觉会产生孤立提示词资源

        行为：
        1. nodes 中的非法 agent_id → 设为 None（节点变成无 Agent 的占位节点）
        2. agent_reshaping 中的非法 agent_id → 记录 warning + 保留原值（不阻断，由 PromptGenerator 自行处理）
        3. 记录到 blueprint._invalid_agent_ids 便于上层重试
        """
        whitelist = self.available_agent_ids
        invalid_map: Dict[str, str] = {}  # invalid_id -> 建议的合法 ID

        # 1. 校验 nodes[].agent_id
        for node in blueprint.nodes:
            if not node.agent_id:
                continue
            if node.agent_id in whitelist:
                continue
            # agent_id 不合法
            suggested = self._suggest_similar_agent(node.agent_id)
            invalid_map[node.agent_id] = suggested or ""
            logger.warning(
                f"🛡️ [WorkflowPlanner] LLM 幻觉 agent_id 已过滤 (node): "
                f"node_id={node.id}, agent_id='{node.agent_id}', "
                f"建议替换为='{suggested or '(无)'}', "
                f"节点类型={node.type}"
            )
            # 清空非法 agent_id，让 AgentFactory 走兜底（避免运行时找不到 agent 崩溃）
            node.agent_id = None

        # 2. 校验 agent_reshaping[].agent_id（提示词生成目标）
        if blueprint.gap_analysis and blueprint.gap_analysis.agent_reshaping:
            for plan in blueprint.gap_analysis.agent_reshaping:
                if not plan.agent_id or plan.agent_id in whitelist:
                    continue
                suggested = self._suggest_similar_agent(plan.agent_id)
                logger.warning(
                    f"🛡️ [WorkflowPlanner] LLM 幻觉 agent_id 已标记 (agent_reshaping): "
                    f"agent_id='{plan.agent_id}', "
                    f"new_role='{plan.new_role}', "
                    f"建议替换为='{suggested or '(无)'}'"
                )
                if plan.agent_id not in invalid_map:
                    invalid_map[plan.agent_id] = suggested or ""

        # 3. 写入 blueprint 私有属性（不再使用动态 setattr）
        if invalid_map:
            blueprint._invalid_agent_ids.update(invalid_map)

            # 写入 summary，告知用户本次自动过滤了哪些幻觉 agent
            note = "\n\n> ⚠️ 自动校验过滤了不存在的 Agent: " + ", ".join(
                f"`{bad}` → `{good or '(无)'}`" for bad, good in invalid_map.items()
            )
            if blueprint.summary:
                blueprint.summary = blueprint.summary + note
            else:
                blueprint.summary = note.lstrip("\n")

    def _suggest_similar_agent(self, invalid_id: str) -> Optional[str]:
        """
        在白名单里找与 invalid_id 字符串最相似的合法 ID（简单编辑距离启发式）。
        """
        if not self._available_agents or not invalid_id:
            return None
        invalid_lower = invalid_id.lower().replace("-", "_")
        best_id: Optional[str] = None
        best_score = 0
        for a in self._available_agents:
            aid = a.get("id", "")
            if not aid:
                continue
            aid_lower = aid.lower()
            # 1) 子串包含直接命中
            if invalid_lower in aid_lower or aid_lower in invalid_lower:
                return aid
            # 2) 简单词集合相似度
            score = self._token_overlap(invalid_lower, aid_lower)
            if score > best_score:
                best_score = score
                best_id = aid
        # 加一个下限避免误匹配
        if best_score >= 0.4:
            return best_id
        return None

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        """粗略的 token 重叠比：按 _ 和 - 拆分后求交集/并集"""
        import re as _re
        ta = {t for t in _re.split(r"[_\-]", a) if t}
        tb = {t for t in _re.split(r"[_\-]", b) if t}
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

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