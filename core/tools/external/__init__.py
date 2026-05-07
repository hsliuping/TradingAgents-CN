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

from importlib import import_module
from typing import Dict


_EXPORT_MAP: Dict[str, str] = {
    # 数据模型
    "BoundaryCheck": ".skill_spec",
    "BusinessRuleFailure": ".skill_spec",
    "BusinessVerificationResult": ".skill_spec",
    "ClarityLevel": ".skill_spec",
    "ConversationRound": ".skill_spec",
    "EvalScore": ".skill_spec",
    "ExpectedOutput": ".skill_spec",
    "GeneratedCode": ".skill_spec",
    "ImplementationFact": ".skill_spec",
    "ImplementationFactReport": ".skill_spec",
    "ImplementationHelper": ".skill_spec",
    "ImplementationIssue": ".skill_spec",
    "IterationRound": ".skill_spec",
    "PipelineResult": ".skill_spec",
    "ReflectionResult": ".skill_spec",
    "SandboxResult": ".skill_spec",
    "SessionStatus": ".skill_spec",
    "SkillCreationSession": ".skill_spec",
    "SkillHandoffContext": ".skill_spec",
    "SkillParameter": ".skill_spec",
    "SkillSource": ".skill_spec",
    "SkillSpec": ".skill_spec",
    "SkillStatus": ".skill_spec",
    "TestCase": ".skill_spec",
    "ValidationResult": ".skill_spec",
    "ValidationCheck": ".skill_spec",
    # 管线模块
    "BusinessVerifier": ".business_verifier",
    "BusinessVerifierRegistry": ".business_verifier",
    "CodeGenerator": ".code_generator",
    "DefaultBusinessVerifier": ".business_verifier",
    "DefaultReconnaissanceController": ".reconnaissance_controller",
    "IterationController": ".iteration_controller",
    "OutputEvaluator": ".output_evaluator",
    "ReconnaissanceController": ".reconnaissance_controller",
    "RequirementAnalyzer": ".requirement_analyzer",
    "SandboxRunner": ".sandbox_runner",
    "StaticValidator": ".static_validator",
    "ValuationBusinessVerifier": ".business_verifier",
}


def __getattr__(name: str):
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(__all__))

__all__ = [
    # 数据模型
    "BoundaryCheck",
    "BusinessRuleFailure",
    "BusinessVerificationResult",
    "ClarityLevel",
    "ConversationRound",
    "EvalScore",
    "ExpectedOutput",
    "GeneratedCode",
    "ImplementationFact",
    "ImplementationFactReport",
    "ImplementationHelper",
    "ImplementationIssue",
    "IterationRound",
    "PipelineResult",
    "ReflectionResult",
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
    "ValidationCheck",
    # 管线模块
    "BusinessVerifier",
    "BusinessVerifierRegistry",
    "CodeGenerator",
    "DefaultBusinessVerifier",
    "DefaultReconnaissanceController",
    "IterationController",
    "OutputEvaluator",
    "ReconnaissanceController",
    "RequirementAnalyzer",
    "SandboxRunner",
    "StaticValidator",
    "ValuationBusinessVerifier",
]
