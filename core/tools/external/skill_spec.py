"""
Skill 生成系统 — 核心数据模型

定义 SkillSpec（需求规格书）、GeneratedCode（生成结果）、
SkillCreationSession（创建会话）等数据模型。
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== 枚举类型 ====================

class ClarityLevel(str, Enum):
    """需求清晰度等级"""
    HIGH = "high"        # 4-5/5 — 1 轮即可
    MEDIUM = "medium"    # 3/5 — 需要 2 轮
    LOW = "low"          # 1-2/5 — 需要 3 轮


class SessionStatus(str, Enum):
    """创建会话状态"""
    GATHERING = "gathering"      # 需求收集中
    CONFIRMED = "confirmed"      # 规格已确认
    GENERATING = "generating"    # 代码生成中
    COMPLETED = "completed"      # 创建完成
    FAILED = "failed"            # 创建失败


class SkillStatus(str, Enum):
    """Skill 状态"""
    ACTIVE = "active"            # 已上线，可使用
    DISABLED = "disabled"        # 已禁用
    DRAFT = "draft"              # 草稿（未通过验证）
    ARCHIVED = "archived"        # 已归档


class SkillSource(str, Enum):
    """Skill 来源"""
    GENERATED = "generated"      # 本系统自动生成
    CLAWHUB = "clawhub"          # 从 ClawHub 导入
    MANUAL = "manual"            # 手动创建


# ==================== 核心数据模型 ====================

class SkillParameter(BaseModel):
    """Skill 参数定义"""
    name: str
    type: str = "string"  # string, integer, float, boolean, list, dict
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class ExpectedOutput(BaseModel):
    """期望输出定义"""
    type: str = "list[dict]"     # 返回值类型
    fields: List[str] = Field(default_factory=list)  # 期望字段列表
    description: str = ""


class SkillSpec(BaseModel):
    """
    Skill 规格书 — 需求沟通阶段的最终产出

    从用户自然语言需求经过多轮对话后锁定的结构化规格，
    是代码生成阶段的唯一输入。

    Skill 表示一个可复用、可验证、边界清晰的功能实现单元，
    不局限于纯数据查询，也可以包含必要的数据整理、确定性计算、
    规则判断、轻量聚合或模板化说明生成。
    """
    tool_id: str                           # 如 "get_eastmoney_news"
    display_name: str                      # 如 "东方财富个股新闻"
    description: str                       # 功能描述（单一明确功能）
    category: str = "utility"              # 分类: news, market, fundamentals 等
    data_source: str = ""                  # 主数据源标识；若有附加来源应在 constraints 中说明
    parameters: List[SkillParameter] = Field(default_factory=list)
    expected_output: ExpectedOutput = Field(default_factory=ExpectedOutput)
    validation_checks: List["ValidationCheck"] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)    # 行为约束
    test_input: Dict[str, Any] = Field(default_factory=dict)  # 测试输入
    test_expected: Dict[str, Any] = Field(default_factory=dict)  # 测试期望
    metadata: Dict[str, Any] = Field(default_factory=dict)       # 生成期附加上下文，不属于最终输出契约
    # 🔧 版本管理字段（迭代模式下写入）
    parent_skill_id: str = ""              # 根 Skill 的 tool_id（首次创建为空，迭代产生的新版本指向原 Skill）
    version: int = 1                       # 版本号（首次创建为 1，迭代递增）
    version_note: str = ""                 # 本次迭代说明（来自用户反馈摘要）


class TestCase(BaseModel):
    """测试用例"""
    input: Dict[str, Any] = Field(default_factory=dict)
    expected_fields: List[str] = Field(default_factory=list)
    expected_type: str = "list"            # list, dict, str


class GeneratedCode(BaseModel):
    """代码生成结果"""
    code: str                              # Python 函数代码
    metadata: Dict[str, Any] = Field(default_factory=dict)  # ToolMetadata 格式
    test_cases: List[TestCase] = Field(default_factory=list)
    generation_model: str = ""             # 生成使用的 LLM 模型
    generation_time: float = 0.0           # 生成耗时（秒）


class ValidationResult(BaseModel):
    """验证结果"""
    passed: bool = False
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class ImplementationHelper(BaseModel):
    """侦察阶段确认可复用的运行时 helper。"""
    module: str = ""
    name: str = ""
    signature: str = ""
    description: str = ""
    reason: str = ""
    # 数据源处理方式标签：
    #   "self_contained" - helper 自包含，内部已封装数据源调用（直接调 Tushare/AKShare 或本地优先+外部兜底），LLM 直接调用即可
    #   "local_only"     - helper 只查本地 MongoDB，若本地无数据 LLM 可能需要自己调外部数据源补充
    #   "partial"        - helper 覆盖部分需求，LLM 可能需要补充其它数据源或计算
    data_source_handling: str = "self_contained"


class ImplementationFact(BaseModel):
    """侦察阶段确认的结构化事实。"""
    source: str = ""
    fact: str = ""
    evidence: str = ""
    field: str = ""
    description: str = ""
    coverage: float | None = None


class ImplementationIssue(BaseModel):
    """实现阶段的限制、禁止路径或运行时缺口。"""
    path: str = ""
    reason: str = ""
    severity: str = "info"  # info, warning, error


class ReconToolTrace(BaseModel):
    """侦察阶段的工具调用轨迹。"""
    tool_name: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    duration_ms: float = 0.0
    result_chars: int = 0
    result_preview: str = ""
    error: str = ""


class ValidationCheck(BaseModel):
    """业务验收或生成前侦察建议的检查项。"""
    name: str = ""
    description: str = ""
    required: bool = True
    check_type: str = "required_field"  # required_field, required_non_empty_payload, custom
    rule_level: str = "data"  # input, output, data, business, warning
    blocking: bool = True
    field: str = ""
    value_path: str = "data"  # output, data
    forbid_null: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class ImplementationFactReport(BaseModel):
    """前置侦察层输出的结构化实现事实报告。"""
    task_summary: str = ""
    recommended_strategy: str = ""
    schema_bundle_context: Dict[str, Any] = Field(default_factory=dict)
    available_helpers: List[ImplementationHelper] = Field(default_factory=list)
    schema_facts: List[ImplementationFact] = Field(default_factory=list)
    sample_fields: Dict[str, List[str]] = Field(default_factory=dict)
    blocked_paths: List[ImplementationIssue] = Field(default_factory=list)
    runtime_gaps: List[ImplementationIssue] = Field(default_factory=list)
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    tool_traces: List[ReconToolTrace] = Field(default_factory=list)
    confidence: float = 0.0
    notes: List[str] = Field(default_factory=list)

    @property
    def has_spec_grounding_facts(self) -> bool:
        """是否包含可落进 spec 的字段级实证事实（helper / 库字段实况 / 样本字段 / schema 契约）。

        用于判断「基于侦察事实二次生成 spec」是否有增量价值：
        无实证事实时二次生成的输入与草稿无实质差异，应跳过以节省一次 LLM 调用。
        """
        return bool(
            self.available_helpers
            or self.schema_facts
            or self.sample_fields
            or self.schema_bundle_context
        )


class EvalScore(BaseModel):
    """评估打分"""
    executability: float = 0.0      # 可执行性 (0-10)
    authenticity: float = 0.0       # 真实性 (0-10)
    completeness: float = 0.0       # 完整性 (0-10)
    relevance: float = 0.0          # 相关性 (0-10)
    format_quality: float = 0.0     # 格式质量 (0-10)
    expert_comment: str = ""        # Judge 专家一句话评语（实时展示给用户）

    @property
    def total(self) -> float:
        """加权总分"""
        weights = [0.25, 0.25, 0.20, 0.20, 0.10]
        scores = [
            self.executability, self.authenticity,
            self.completeness, self.relevance, self.format_quality,
        ]
        return round(sum(w * s for w, s in zip(weights, scores)), 2)



class SandboxResult(BaseModel):
    """沙箱执行结果"""
    success: bool = False
    output: Any = None                     # 函数返回值
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0            # 秒
    error: Optional[str] = None


class ReflectionResult(BaseModel):
    """LLM 反思分析结果 — 在迭代失败时对根因进行深度分析"""
    root_cause: str = ""
    fix_plan: List[str] = Field(default_factory=list)
    should_retry: bool = True
    confidence: float = 0.5


class BusinessRuleFailure(BaseModel):
    """业务验收失败项。"""
    rule_id: str = ""
    message: str = ""
    severity: str = "error"  # warning, error


class BusinessVerificationResult(BaseModel):
    """业务验收结果。"""
    passed: bool = True
    business_score: float = 0.0
    failures: List[BusinessRuleFailure] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class IterationRound(BaseModel):
    """单轮迭代记录"""
    round_number: int = 1
    generated_code: Optional[GeneratedCode] = None
    validation: Optional[ValidationResult] = None
    sandbox: Optional[SandboxResult] = None
    eval_score: Optional[EvalScore] = None
    business_verification: Optional[BusinessVerificationResult] = None
    reflection: Optional[ReflectionResult] = None
    feedback: str = ""                     # 给下一轮的反馈
    decision: str = ""                     # PASS / RETRY / FAIL


class PipelineResult(BaseModel):
    """管线最终结果"""
    success: bool = False
    tool_id: str = ""
    final_code: str = ""
    final_metadata: Dict[str, Any] = Field(default_factory=dict)
    iterations: List[IterationRound] = Field(default_factory=list)
    total_rounds: int = 0
    total_time: float = 0.0
    error: Optional[str] = None


class BoundaryCheck(BaseModel):
    """边界检测结果"""
    within_boundary: bool = True
    complexity_score: int = 1              # 1-5
    concerns: List[str] = Field(default_factory=list)
    decomposition_suggestions: List[str] = Field(default_factory=list)


class ConversationRound(BaseModel):
    """对话轮次"""
    round_number: int
    ai_message: str = ""                   # AI 回复（功能点确认 / 技术方案 / 规格确认）
    user_message: str = ""                 # 用户回复
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SkillHandoffContext(BaseModel):
    """来自上游工坊或流程的交接上下文。"""
    source: str = ""
    source_spec_id: str = ""
    source_name: str = ""
    target_capability: str = ""
    handoff_intent: str = ""
    # Agent Studio 缺口补齐的反向追溯字段（Phase 2）
    user_id: str = ""                # 发起补齐的真实用户，决定 Skill 归属与权限
    workshop_session_id: str = ""    # 来源 Agent 工坊会话
    spec_id: str = ""                # 来源 Agent 规格
    version_id: str = ""             # 来源 Agent 版本（如已生成）
    gap_id: str = ""                 # 来源能力缺口标识
    agent_name: str = ""             # 来源 Agent 名称
    agent_goal: str = ""             # 来源 Agent 主要目标
    searched_capabilities: List[str] = Field(default_factory=list)      # 上游已检索/评估过的能力
    confirmed_data_sources: List[str] = Field(default_factory=list)     # 上游已确认可用的数据源或 helper
    user_clarifications: List[str] = Field(default_factory=list)        # 用户在上游澄清过的关键结论
    gap_context: str = ""                                           # 当前 gap 的上下文摘要
    related_gaps: List[str] = Field(default_factory=list)              # 同一次补齐任务中的相关 gap
    known_failure_summaries: List[str] = Field(default_factory=list)  # 同一次 job 内已知失败摘要
    known_verified_facts: List[str] = Field(default_factory=list)      # 同一次 job 内已验证环境事实


class PipelineProgressEvent(BaseModel):
    """生成管线进度事件。"""
    stage: str = ""
    message: str = ""
    iteration: int = 0
    progress: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SkillCreationSession(BaseModel):
    """
    Skill 创建会话 — 对应 MongoDB skill_creation_sessions 集合

    记录从需求沟通到创建完成的完整过程。
    """
    session_id: str                        # UUID
    user_id: str = ""
    status: SessionStatus = SessionStatus.GATHERING
    # 需求沟通
    rounds: List[ConversationRound] = Field(default_factory=list)
    current_round: int = 0
    clarity_level: Optional[ClarityLevel] = None
    boundary_check: Optional[BoundaryCheck] = None
    handoff_context: Optional[SkillHandoffContext] = None
    # 迭代模式：记录正在迭代的 Skill 的 tool_id
    iterate_skill_id: Optional[str] = None
    # 规格
    spec: Optional[SkillSpec] = None
    spec_confirmed: bool = False
    # 侦察报告（侦察前置模式缓存）
    fact_report: Optional[ImplementationFactReport] = None
    # 生成结果
    pipeline_result: Optional[PipelineResult] = None
    pipeline_history: List[PipelineResult] = Field(default_factory=list)
    pipeline_stage: str = ""
    pipeline_message: str = ""
    pipeline_iteration: int = 0
    pipeline_progress: float = 0.0
    pipeline_details: List[PipelineProgressEvent] = Field(default_factory=list)
    # 时间
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

