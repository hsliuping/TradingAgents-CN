"""
工作流生成数据模型

定义 AI 工作流生成过程中使用的所有数据结构。
包括会话状态、对话轮次、缺口分析、蓝图结构等。

参考: docs/05-design/v3.0/ai-workflow-generation.md
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, PrivateAttr


# ==================== 枚举类型 ====================

class GenerationSessionStatus(str, Enum):
    """工作流生成会话状态"""
    GATHERING = "gathering"              # 收集需求中（对话进行中）
    PLANNING = "planning"                # AI 正在规划（生成蓝图中）
    BLUEPRINT_READY = "blueprint_ready"  # 蓝图已生成，等待用户确认
    CONFIRMED = "confirmed"              # 用户已确认
    COMPLETING = "completing"            # 自动补全中（创建 Skill + 生成提示词）
    CREATING = "creating"                # 正在创建工作流
    COMPLETED = "completed"              # 创建完成（草稿状态，需发布）
    PUBLISHED = "published"              # 已发布（资源已激活为正式版本）
    OPTIMIZING = "optimizing"            # 迭代优化中
    FAILED = "failed"                    # 失败


# ==================== 基础数据模型 ====================

class ConversationRound(BaseModel):
    """对话轮次"""
    round_num: int = 0
    user_message: str = ""
    ai_message: str = ""
    phase: str = "gathering"             # gathering / optimizing（区分创建和优化阶段）
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlannedNode(BaseModel):
    """规划的节点"""
    id: str
    type: str                            # start, end, analyst, researcher, trader, risk, manager,
    #                                      parallel, merge, debate, post_processor, condition
    agent_id: Optional[str] = None       # 关联的 Agent ID（来自 BUILTIN_AGENTS）
    label: str = ""
    position_x: float = 0
    position_y: float = 0
    config: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""                # AI 对该节点的说明（展示给用户）


class PlannedEdge(BaseModel):
    """规划的边"""
    id: str
    source: str                          # 源节点 ID
    target: str                          # 目标节点 ID
    label: Optional[str] = None
    animated: bool = False
    type: Optional[str] = "normal"       # edge 类型（normal/conditional）
    condition: Optional[str] = None      # 条件表达（"true"/"false"）


# ==================== 缺口分析模型 ====================

class AgentReshapingPlan(BaseModel):
    """Agent 能力重塑计划 — 通过提示词改变 Agent 在工作流中的角色"""
    agent_id: str                        # 选用的现有 Agent（如 market_analyst）
    node_id: str = ""                    # 🆕 对应工作流节点 ID（同一 agent 在不同节点有不同提示词）
    original_role: str = ""              # 原始角色描述
    new_role: str = ""                   # 在本工作流中的新角色（如"可转债市场分析师"）
    reshaping_direction: str = ""        # 简述定制方向（一句话）
    key_focus_areas: List[str] = Field(default_factory=list)  # 关键分析维度（3-6 项）
    prompt_changes: Dict[str, str] = Field(default_factory=dict)  # 兼容旧格式：完整提示词草案
    additional_tools: List[str] = Field(default_factory=list)     # 需要额外绑定的工具 ID


class SkillCreationRequest(BaseModel):
    """Skill 自动创建请求"""
    skill_name: str                      # 期望的 Skill 名称
    skill_description: str = ""          # 功能描述
    target_agent_id: str = ""            # 要绑定到哪个 Agent
    priority: str = "required"           # required / optional
    generated_skill_id: Optional[str] = None  # 创建成功后回填
    status: str = "pending"              # pending / creating / completed / failed
    error: Optional[str] = None          # 失败原因


class GapAnalysisResult(BaseModel):
    """缺口分析结果 — AI 自动检测后生成"""

    # Agent 能力缺口（不需要创建新 Agent，通过提示词重塑解决）
    agent_reshaping: List[AgentReshapingPlan] = Field(default_factory=list)

    # 使用默认提示词的 Agent（无需定制）
    agents_using_default: List[Dict[str, str]] = Field(default_factory=list)  # [{id, name, reason}]

    # 工具/Skill 缺口（需要自动创建新 Skill）
    missing_skills: List[SkillCreationRequest] = Field(default_factory=list)

    # 现有资源可直接使用的
    available_agents: List[Dict[str, str]] = Field(default_factory=list)  # [{id, name, role_in_workflow}]
    available_tools: List[Dict[str, str]] = Field(default_factory=list)   # [{id, name, used_by_agent}]

    # 分析说明
    analysis_summary: str = ""


# ==================== 蓝图模型 ====================

class WorkflowBlueprint(BaseModel):
    """
    AI 生成的工作流蓝图 — 包含结构 + 缺口分析 + 补全计划

    用户确认后，系统自动执行提示词生成和 Skill 创建，
    然后将蓝图转换为 WorkflowDefinition 保存。
    """

    # 基本信息
    name: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)

    # 🛡️ 防幻觉：记录白名单校验中发现的非法 agent_id 及其建议替换（PrivateAttr，不参与序列化）
    _invalid_agent_ids: Dict[str, str] = PrivateAttr(default_factory=dict)

    # 工作流结构
    nodes: List[PlannedNode] = Field(default_factory=list)
    edges: List[PlannedEdge] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

    # 🆕 输入参数定义（前端根据此字段动态生成执行表单）
    input_config: Dict[str, Any] = Field(default_factory=lambda: {"fields": []})

    # AI 方案说明
    summary: str = ""                    # 方案概述
    rationale: str = ""                  # 设计思路

    # 缺口分析
    gap_analysis: Optional[GapAnalysisResult] = None

    # 提示词生成计划 — 每个需要定制的 Agent 的提示词草案
    prompt_plans: List[Dict[str, Any]] = Field(default_factory=list)

    # 创建进度跟踪
    creation_progress: Dict[str, Any] = Field(default_factory=lambda: {
        "skills_total": 0,
        "skills_completed": 0,
        "prompts_total": 0,
        "prompts_completed": 0,
        "workflow_created": False,
    })


# ==================== 会话模型 ====================

class WorkflowGenerationSession(BaseModel):
    """
    工作流生成会话 — 对应 MongoDB workflow_generation_sessions 集合

    记录从需求沟通到工作流创建完成的完整过程，
    支持迭代优化。
    """
    session_id: str
    user_id: str = ""
    status: GenerationSessionStatus = GenerationSessionStatus.GATHERING

    # 对话记录
    rounds: List[ConversationRound] = Field(default_factory=list)
    current_round: int = 0

    # AI 生成的蓝图
    blueprint: Optional[WorkflowBlueprint] = None
    blueprint_confirmed: bool = False

    # 创建结果
    workflow_id: Optional[str] = None          # 创建成功后的工作流 ID
    created_prompt_ids: List[str] = Field(default_factory=list)  # 创建的提示词模板 ID
    created_skill_ids: List[str] = Field(default_factory=list)   # 创建的 Skill ID
    creation_report: Optional[Dict[str, Any]] = None  # 创建报告（持久化，供恢复时展示）
    error: Optional[str] = None

    # 优化记录
    optimize_rounds: List[ConversationRound] = Field(default_factory=list)
    optimize_count: int = 0

    # 时间
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

