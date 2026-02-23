"""
AI 智能工作流生成器

通过自然语言对话，结合系统中可用的 Agent、Tool、Skill、提示词模板，
自动生成完整的 WorkflowDefinition 及相关绑定。
"""

from .workflow_spec import (
    WorkflowGenerationSession,
    WorkflowBlueprint,
    GenerationSessionStatus,
    ConversationRound,
    PlannedNode,
    PlannedEdge,
    AgentReshapingPlan,
    SkillCreationRequest,
    GapAnalysisResult,
)
from .resource_collector import ResourceCollector
from .workflow_planner import WorkflowPlanner
from .prompt_generator import PromptGenerator
from .skill_orchestrator import SkillOrchestrator

__all__ = [
    # 数据模型
    "WorkflowGenerationSession",
    "WorkflowBlueprint",
    "GenerationSessionStatus",
    "ConversationRound",
    "PlannedNode",
    "PlannedEdge",
    "AgentReshapingPlan",
    "SkillCreationRequest",
    "GapAnalysisResult",
    # 核心模块
    "ResourceCollector",
    "WorkflowPlanner",
    "PromptGenerator",
    "SkillOrchestrator",
]

