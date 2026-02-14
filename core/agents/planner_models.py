"""
规划分析数据模型

定义 Plan-then-Execute 模式中使用的所有 Pydantic 模型：
- PlanStep: 计划中的单个步骤
- AnalysisPlan: 完整的分析计划
- StepResult: 步骤执行结果
- SupplementRequest: 补充调用请求
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanSource(str, Enum):
    """计划来源"""
    SEED_FLOW = "seed_flow"       # 第一级：种子流程匹配
    LLM_PLAN = "llm_plan"         # 第二级：LLM 自主规划
    REACT_FALLBACK = "react"      # 第三级：ReAct 回退


class PlanStep(BaseModel):
    """计划中的单个步骤"""
    id: int = Field(..., description="步骤编号，从 1 开始")
    tool: str = Field(..., description="工具 ID（必须在 ToolRegistry 中存在）")
    args: Dict[str, Any] = Field(default_factory=dict, description="工具调用参数")
    intent: str = Field("", description="该步骤的意图说明，帮助综合阶段理解语义")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID 列表，空列表表示无依赖可并行")


class AnalysisPlan(BaseModel):
    """完整的分析计划"""
    question: str = Field(..., description="用户原始问题")
    template_id: Optional[str] = Field(None, description="种子流程 ID（第一级匹配时非空，第二级为 null）")
    source: PlanSource = Field(PlanSource.LLM_PLAN, description="计划来源")
    steps: List[PlanStep] = Field(default_factory=list, description="计划步骤列表")

    @property
    def parallel_groups(self) -> List[List[PlanStep]]:
        """
        按依赖关系分组，同组内可并行执行。
        返回有序的步骤组列表（拓扑排序）。
        """
        if not self.steps:
            return []

        completed: set = set()
        groups: List[List[PlanStep]] = []
        remaining = list(self.steps)

        while remaining:
            # 找到所有依赖已完成的步骤
            ready = [s for s in remaining if all(d in completed for d in s.depends_on)]
            if not ready:
                # 存在循环依赖，把剩余步骤全部放入一组串行执行
                groups.append(remaining)
                break
            groups.append(ready)
            for s in ready:
                completed.add(s.id)
                remaining.remove(s)

        return groups


class StepResult(BaseModel):
    """步骤执行结果"""
    step_id: int = Field(..., description="对应的步骤 ID")
    tool: str = Field(..., description="执行的工具 ID")
    intent: str = Field("", description="步骤意图")
    success: bool = Field(True, description="是否执行成功")
    result: Any = Field(None, description="工具返回结果")
    error: Optional[str] = Field(None, description="错误信息（失败时）")
    duration_ms: int = Field(0, description="执行耗时（毫秒）")


class SupplementRequest(BaseModel):
    """补充调用请求（综合阶段 LLM 判定数据不足时生成）"""
    reason: str = Field(..., description="需要补充的原因")
    steps: List[PlanStep] = Field(default_factory=list, description="补充步骤（最多 2 个）")


class PlannedAnalysisResult(BaseModel):
    """规划分析最终结果"""
    reply: str = Field(..., description="最终回答")
    plan: Optional[AnalysisPlan] = Field(None, description="执行的分析计划")
    tools_used: List[str] = Field(default_factory=list, description="使用的工具列表")
    step_results: List[StepResult] = Field(default_factory=list, description="各步骤执行结果")
    source: PlanSource = Field(PlanSource.LLM_PLAN, description="实际使用的分析来源")
    supplemented: bool = Field(False, description="是否进行了补充调用")
    data_refs: Optional[List] = Field(None, description="引用的数据，预留")

