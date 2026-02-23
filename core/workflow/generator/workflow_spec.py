"""
工作流生成数据模型

定义 AI 工作流生成过程中使用的所有数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerationSessionStatus(str, Enum):
    """工作流生成会话状态"""
    GATHERING = "gathering"       # 收集需求中
    PLANNING = "planning"         # AI 规划中
    PLAN_READY = "plan_ready"     # 方案已生成，等待用户确认
    CONFIRMED = "confirmed"       # 用户已确认
    CREATING = "creating"         # 正在创建工作流
    COMPLETED = "completed"       # 创建完成
    FAILED = "failed"             # 失败


class ConversationRound(BaseModel):
    """对话轮次"""
    round_num: int = 0
    user_message: str = ""
    ai_message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlannedNode(BaseModel):
    """规划的节点"""
    id: str
    type: str                                # start, end, analyst, researcher, trader, risk, manager, parallel, merge, debate
    agent_id: Optional[str] = None           # 关联的 Agent ID
    label: str = ""
    position_x: float = 0
    position_y: float = 0
    config: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""                    # AI 对该节点的说明


class PlannedEdge(BaseModel):
    """规划的边"""
    id: str
    source: str
    target: str
    label: Optional[str] = None
    animated: bool = False


class PlannedBinding(BaseModel):
    """规划的 Agent-Workflow 绑定"""
    agent_id: str
    order: int = 0
    parallel_group: Optional[str] = None
    tool_overrides: List[str] = Field(default_factory=list)
    description: str = ""                    # AI 对绑定的说明


class WorkflowPlan(BaseModel):
    """
    AI 生成的工作流方案

    包含完整的节点、边、绑定信息，
    用户确认后转换为 WorkflowDefinition。
    """
    name: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)

    # 工作流结构
    nodes: List[PlannedNode] = Field(default_factory=list)
    edges: List[PlannedEdge] = Field(default_factory=list)

    # Agent 绑定
    agent_bindings: List[PlannedBinding] = Field(default_factory=list)

    # 工作流配置
    config: Dict[str, Any] = Field(default_factory=dict)

    # AI 方案说明
    summary: str = ""                        # 方案整体说明
    rationale: str = ""                      # 设计思路

    # 使用的资源列表（展示给用户看）
    used_agents: List[Dict[str, str]] = Field(default_factory=list)   # [{id, name, description}]
    used_tools: List[Dict[str, str]] = Field(default_factory=list)    # [{id, name, description}]


class WorkflowGenerationSession(BaseModel):
    """
    工作流生成会话 — 对应 MongoDB workflow_generation_sessions 集合

    记录从需求沟通到工作流创建完成的完整过程。
    """
    session_id: str
    user_id: str = ""
    status: GenerationSessionStatus = GenerationSessionStatus.GATHERING

    # 对话记录
    rounds: List[ConversationRound] = Field(default_factory=list)
    current_round: int = 0

    # AI 生成的方案
    plan: Optional[WorkflowPlan] = None
    plan_confirmed: bool = False

    # 创建结果
    workflow_id: Optional[str] = None        # 创建成功后的工作流 ID
    error: Optional[str] = None

    # 时间
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

