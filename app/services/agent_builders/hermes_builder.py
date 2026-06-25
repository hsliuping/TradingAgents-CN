"""
Hermes Builder Provider（预留）

未来接入 Hermes 作为 Agent 构建器时的实现占位。
Hermes 的优势：天然学习循环，可沉淀构建经验。
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.agent_builders.base import AgentBuilderDraft, AgentBuilderProvider

logger = logging.getLogger("webapi")


class HermesBuilderProvider(AgentBuilderProvider):
    """基于 Hermes 的构建器实现（预留，未接入）"""

    def __init__(self, hermes_client=None):
        self._client = hermes_client

    @property
    def provider_name(self) -> str:
        return "hermes"

    async def clarify_requirements(
        self,
        *,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("Hermes 尚未接入，请使用 EmbeddedNanobotBuilderProvider")

    async def analyze_gaps(
        self,
        *,
        spec: Dict[str, Any],
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("Hermes 尚未接入，请使用 EmbeddedNanobotBuilderProvider")

    async def plan_tooling(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("Hermes 尚未接入，请使用 EmbeddedNanobotBuilderProvider")

    async def build_draft(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        tooling_plan: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AgentBuilderDraft:
        raise NotImplementedError("Hermes 尚未接入，请使用 EmbeddedNanobotBuilderProvider")
