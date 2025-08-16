"""
帝国AI核心模块
Imperial Agents Core Module
"""

from .imperial_agent_wrapper import (
    ImperialAgentWrapper,
    AnalysisResult,
    RoleConfig,
    AnalysisType,
    DecisionLevel,
    ImperialAgentFactory
)

from .seven_stage_collision_engine import (
    SevenStageCollisionEngine,
    CollisionStage,
    CollisionOpinion,
    CollisionResult
)

__all__ = [
    'ImperialAgentWrapper',
    'AnalysisResult', 
    'RoleConfig',
    'AnalysisType',
    'DecisionLevel',
    'ImperialAgentFactory',
    'SevenStageCollisionEngine',
    'CollisionStage',
    'CollisionOpinion',
    'CollisionResult'
]
