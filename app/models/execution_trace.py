"""Agent 执行轨迹数据模型（P1: 机器可读执行轨迹）

每次 manager agent 执行时产出一份结构化轨迹，存入 MongoDB agent_execution_traces 集合，
为 P2「反思→可执行断言」提供数据基础（后台扫描失败模式、回归测试、效果度量）。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.timezone import now_tz


class LLMConfigSnapshot(BaseModel):
    """LLM 配置快照"""
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class TokenUsage(BaseModel):
    """Token 用量"""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class PromptSnapshot(BaseModel):
    """提示词快照（只存哈希和长度，不存全文）"""
    system_prompt_hash: Optional[str] = None    # SHA256 前 16 位
    system_prompt_length: int = 0
    user_prompt_hash: Optional[str] = None
    user_prompt_length: int = 0


class InputSnapshot(BaseModel):
    """输入快照"""
    input_keys: List[str] = Field(default_factory=list)
    input_lengths: Dict[str, int] = Field(default_factory=dict)


class OutputSnapshot(BaseModel):
    """输出快照"""
    output_raw_length: int = 0
    output_raw_preview: Optional[str] = None  # 前 500 字符，调试用
    output_parsed_keys: List[str] = Field(default_factory=list)
    output_parsed_success: Optional[bool] = None
    output_parsed_type: Optional[str] = None  # dict / str / etc.


class ValidationResult(BaseModel):
    """校验结果（子类回填）"""
    validation_status: Optional[str] = None    # "passed" / "failed" / None
    validation_error: Optional[str] = None
    validation_details: Optional[Dict[str, Any]] = None


class AgentExecutionTrace(BaseModel):
    """Agent 执行轨迹（机器可读）

    设计原则：
    1. 只存哈希/长度/摘要，不存 prompt 全文（避免膨胀）
    2. output_raw_preview 存前 500 字符（调试用）
    3. validation_status 由子类 update_one 回填
    4. metadata 预留 P2 扩展（failure_mode / assertions / regression_test_id）
    """

    # 标识
    trace_id: str = Field(..., description="UUID，唯一标识一次执行")
    schema_version: str = Field(default="1.0", description="轨迹 schema 版本")

    # Agent 元数据
    agent_id: str
    agent_version: str = "unknown"
    agent_type: str = "manager"               # "manager" / "trader"
    manager_type: Optional[str] = None        # "risk" / "research"

    # 工作流上下文（从 state["_workflow_runtime"] 提取）
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    thread_id: Optional[str] = None

    # 分析目标
    ticker: Optional[str] = None
    analysis_date: Optional[str] = None

    # LLM 配置
    llm_config: LLMConfigSnapshot = Field(default_factory=LLMConfigSnapshot)

    # 输入
    inputs: InputSnapshot = Field(default_factory=InputSnapshot)

    # 提示词
    prompts: PromptSnapshot = Field(default_factory=PromptSnapshot)

    # LLM 输出
    output: OutputSnapshot = Field(default_factory=OutputSnapshot)

    # Token 用量
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    # 校验结果（子类回填）
    validation: ValidationResult = Field(default_factory=ValidationResult)

    # 执行状态
    success: bool = True
    error_message: Optional[str] = None
    error_type: Optional[str] = None

    # 时间
    started_at: datetime = Field(default_factory=now_tz)
    finished_at: Optional[datetime] = None
    execution_duration_ms: Optional[int] = None
    llm_duration_ms: Optional[int] = None

    # 扩展（P2 预留）
    metadata: Dict[str, Any] = Field(default_factory=dict)
