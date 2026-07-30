"""Agent 断言数据模型（P2: 反思 lesson 升级为可执行断言）

从失败执行轨迹提炼的机器可执行规则，存入 MongoDB agent_assertions 集合。
在 manager agent 校验时同步执行，违规结果合并到 validation_status。

与反思 lesson（mem0 中的文本经验）解耦：
- lesson 是"人类可读经验"，注入 prompt，LLM 消费
- 断言是"机器可执行规则"，注入校验器，Python 消费
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.timezone import now_tz


class AssertionType(str, Enum):
    """断言类型（可扩展）"""
    TERM_FORBIDDEN = "term_forbidden"        # 原始文本中禁止出现某些术语
    FIELD_REQUIRED = "field_required"        # parsed_dict 必须包含字段
    FIELD_ENUM = "field_enum"                # 字段值必须在枚举内
    FIELD_RANGE = "field_range"              # 数值字段必须在范围内
    SCHEMA_MATCH = "schema_match"            # 整个 parsed_dict 必须匹配 schema
    REGEX_MATCH = "regex_match"              # 字段必须匹配正则
    SECTION_REQUIRED = "section_required"    # 原始文本必须包含章节标题


class AssertionSeverity(str, Enum):
    """断言严重级别"""
    ERROR = "error"      # 影响 validation_status（降级为 failed）
    WARNING = "warning"  # 仅记录到 assertion_violations 字段


class AssertionConstraint(BaseModel):
    """按 assertion_type 不同的约束 payload（自由 dict）。

    约束示例：
    - term_forbidden: {"terms": ["看涨", "看跌"]}
    - field_required: {"field": "risk_level"}
    - field_enum: {"field": "final_trade_decision.action", "allowed": ["乐观","审慎","中性"]}
    - field_range: {"field": "confidence", "min": 0.0, "max": 1.0}
    - schema_match: {"schema_name": "RiskAssessmentOutput"}
    - regex_match: {"field": "summary", "pattern": r"\\d{4}-\\d{2}-\\d{2}"}
    - section_required: {"sections": ["一句话结论", "核心依据"]}
    """
    model_config = {"extra": "allow"}


class AgentAssertion(BaseModel):
    """断言定义"""

    # 标识
    assertion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "1.0"

    # 目标
    target_agent: str                        # agent_id，如 "risk_manager_v2"
    assertion_type: AssertionType
    target_field: str = "*"                  # 字段路径（点路径如 final_trade_decision.action），"*" 表示作用于原始文本
    constraint: AssertionConstraint

    # 行为
    severity: AssertionSeverity = AssertionSeverity.WARNING
    enabled: bool = False                    # 默认 false，需人工激活
    description: str = ""                    # 人类可读说明

    # 来源（自动生成时填充）
    source_trace_id: Optional[str] = None
    source_failure_pattern: Optional[str] = None
    creator: str = "manual"                  # "manual" / "auto_generator"

    # 统计
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None

    # 时间
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)


class AssertionViolation(BaseModel):
    """断言执行结果（一条断言对应一条 violation，未违规则不产生）"""
    assertion_id: str
    assertion_type: AssertionType
    target_agent: str
    severity: AssertionSeverity
    description: str
    violation_detail: str                    # 具体违规信息（如命中的术语列表）


class AssertionRunResult(BaseModel):
    """一次 agent 执行的断言运行结果"""
    ran: bool = False                        # 是否真的执行了断言（False 表示无启用断言或加载失败）
    violations: List[AssertionViolation] = Field(default_factory=list)
    has_error_violation: bool = False        # 是否存在 error 级别违规
    error_count: int = 0
    warning_count: int = 0
    executed_at: datetime = Field(default_factory=now_tz)
