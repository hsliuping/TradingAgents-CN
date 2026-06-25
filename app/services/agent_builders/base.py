"""
Agent Builder Provider 抽象接口与 DTO

所有构建器实现必须继承 AgentBuilderProvider 并实现其抽象方法。
AgentWorkshopService 通过此接口与构建器交互，不感知底层实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentBuilderDraft:
    """构建器产出的 Agent 草案，包含运行时契约"""

    agent_id: str
    agent_name: str
    description: str

    # 运行时契约
    runtime_contract: Dict[str, Any] = field(default_factory=dict)
    prompt_contract: Dict[str, Any] = field(default_factory=dict)
    tooling_contract: Dict[str, Any] = field(default_factory=dict)

    # 规格信息
    primary_goal: str = ""
    domain: str = "stock_analysis"
    outputs: List[str] = field(default_factory=list)
    non_goals: List[str] = field(default_factory=list)
    preferred_methods: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    target_users: List[str] = field(default_factory=list)

    # 工具
    tool_ids: List[str] = field(default_factory=list)

    # 会话信息
    source_thread_id: str = ""
    owner_user_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "runtime_contract": self.runtime_contract,
            "prompt_contract": self.prompt_contract,
            "tooling_contract": self.tooling_contract,
            "primary_goal": self.primary_goal,
            "domain": self.domain,
            "outputs": self.outputs,
            "non_goals": self.non_goals,
            "preferred_methods": self.preferred_methods,
            "constraints": self.constraints,
            "target_users": self.target_users,
            "tool_ids": self.tool_ids,
            "source_thread_id": self.source_thread_id,
            "owner_user_id": self.owner_user_id,
        }


class AgentBuilderProvider(ABC):
    """Agent 构建器抽象接口

    所有构建器实现必须提供以下方法：
    - clarify_requirements: 需求澄清
    - analyze_gaps: 缺口分析
    - plan_tooling: 工具规划
    - build_draft: 生成 Agent 草案（含运行时契约）
    """

    @abstractmethod
    async def clarify_requirements(
        self,
        *,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """需求澄清：分析用户输入，返回结构化需求理解"""
        ...

    @abstractmethod
    async def analyze_gaps(
        self,
        *,
        spec: Dict[str, Any],
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """缺口分析：对比规格与可用资源，返回缺口报告"""
        ...

    @abstractmethod
    async def plan_tooling(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """工具规划：根据缺口报告和可用工具，返回工具方案"""
        ...

    @abstractmethod
    async def build_draft(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        tooling_plan: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AgentBuilderDraft:
        """生成 Agent 草案：包含完整的运行时契约"""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """构建器名称，用于日志和调试"""
        ...
