"""
外部 Skill 生成系统

提供 Skill 需求分析、代码生成、验证、评估和迭代控制的完整管线。

使用方法::

    from core.tools.external import RequirementAnalyzer, IterationController

    # 1. 需求沟通
    analyzer = RequirementAnalyzer(provider="deepseek")
    session = analyzer.create_session(user_id="u1")
    session, reply = analyzer.process_user_input(session, "我需要获取个股新闻")

    # 2. 确认规格后，生成代码
    session, spec = analyzer.confirm_spec(session, "确认")

    # 3. 迭代生成
    controller = IterationController(provider="deepseek")
    result = controller.run(spec)
"""

# 数据模型
from .skill_spec import (
    BoundaryCheck,
    ClarityLevel,
    ConversationRound,
    EvalScore,
    ExpectedOutput,
    GeneratedCode,
    IterationRound,
    PipelineResult,
    SandboxResult,
    SessionStatus,
    SkillCreationSession,
    SkillHandoffContext,
    SkillParameter,
    SkillSource,
    SkillSpec,
    SkillStatus,
    TestCase,
    ValidationResult,
)

# 管线模块
from .code_generator import CodeGenerator
from .iteration_controller import IterationController
from .output_evaluator import OutputEvaluator
from .requirement_analyzer import RequirementAnalyzer
from .sandbox_runner import SandboxRunner
from .static_validator import StaticValidator

__all__ = [
    # 数据模型
    "BoundaryCheck",
    "ClarityLevel",
    "ConversationRound",
    "EvalScore",
    "ExpectedOutput",
    "GeneratedCode",
    "IterationRound",
    "PipelineResult",
    "SandboxResult",
    "SessionStatus",
    "SkillCreationSession",
    "SkillHandoffContext",
    "SkillParameter",
    "SkillSource",
    "SkillSpec",
    "SkillStatus",
    "TestCase",
    "ValidationResult",
    # 管线模块
    "CodeGenerator",
    "IterationController",
    "OutputEvaluator",
    "RequirementAnalyzer",
    "SandboxRunner",
    "StaticValidator",
]
