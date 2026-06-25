"""
Embedded Nanobot Builder Provider

封装 EmbeddedNanobotRuntime，作为 Agent 工坊的主力构建器。
通过 Nanobot 的对话能力驱动需求澄清、缺口分析、工具规划和 Agent 草案生成。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.agent_builders.base import AgentBuilderDraft, AgentBuilderProvider

logger = logging.getLogger("webapi")


class EmbeddedNanobotBuilderProvider(AgentBuilderProvider):
    """基于 Embedded Nanobot 的构建器实现（当前主力）"""

    def __init__(self, nanobot_runtime=None):
        self._runtime = nanobot_runtime

    @property
    def provider_name(self) -> str:
        return "embedded_nanobot"

    async def _ensure_runtime(self):
        if self._runtime is None:
            from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
            self._runtime = EmbeddedNanobotRuntime()
        return self._runtime

    async def _call_nanobot(
        self,
        user_message: str,
        session_key: str = "embedded:agent-builder",
        thread_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        runtime = await self._ensure_runtime()
        result = await runtime.handle_message(
            user_message=user_message,
            session_key=session_key,
            thread_context=thread_context or {},
        )
        return result

    async def clarify_requirements(
        self,
        *,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            result = await self._call_nanobot(
                user_message=user_message,
                thread_context={"stage": "clarify_requirements", "current_spec": current_spec},
            )
            response_text = str(result.get("response", "") or "")
            # 尝试解析 JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return {
                    "agent_name": "未命名 Agent",
                    "primary_goal": user_message[:200],
                    "domain": "stock_analysis",
                    "outputs": ["analysis_report"],
                    "pending_questions": ["请更详细地描述这个 Agent 的职责"],
                    "completeness_score": 0.3,
                }
        except Exception as e:
            logger.warning("[NanobotBuilder] 需求澄清失败: %s", e)
            return {
                "agent_name": "未命名 Agent",
                "primary_goal": user_message[:200],
                "domain": "stock_analysis",
                "outputs": ["analysis_report"],
                "pending_questions": ["请更详细地描述这个 Agent 的职责"],
                "completeness_score": 0.3,
            }

    async def analyze_gaps(
        self,
        *,
        spec: Dict[str, Any],
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        try:
            prompt = f"分析以下 Agent 规格的资源缺口：\n{json.dumps(spec, ensure_ascii=False)}"
            if available_tools:
                prompt += f"\n可用工具：{json.dumps(available_tools, ensure_ascii=False)}"
            result = await self._call_nanobot(
                user_message=prompt,
                thread_context={"stage": "analyze_gaps"},
            )
            response_text = str(result.get("response", "") or "")
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return {"data_gaps": [], "tool_gaps": [], "capability_gaps": [], "severity": "low"}
        except Exception as e:
            logger.warning("[NanobotBuilder] 缺口分析失败: %s", e)
            return {"data_gaps": [], "tool_gaps": [], "capability_gaps": [], "severity": "low"}

    async def plan_tooling(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        try:
            prompt = f"为以下 Agent 规格规划工具方案：\n{json.dumps(spec, ensure_ascii=False)}"
            if gap_report:
                prompt += f"\n缺口报告：{json.dumps(gap_report, ensure_ascii=False)}"
            result = await self._call_nanobot(
                user_message=prompt,
                thread_context={"stage": "plan_tooling"},
            )
            response_text = str(result.get("response", "") or "")
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return {"required_tools": [], "default_tools": [], "missing_capabilities": []}
        except Exception as e:
            logger.warning("[NanobotBuilder] 工具规划失败: %s", e)
            return {"required_tools": [], "default_tools": [], "missing_capabilities": []}

    async def build_draft(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        tooling_plan: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AgentBuilderDraft:
        agent_id = spec.get("agent_id", "custom_agent_v1")
        agent_name = spec.get("agent_name", spec.get("name", "未命名 Agent"))
        description = spec.get("primary_goal", spec.get("description", ""))

        # 通过 Nanobot 生成运行时契约
        try:
            prompt = (
                f"为以下 Agent 生成完整的运行时契约（JSON）：\n"
                f"规格：{json.dumps(spec, ensure_ascii=False)}\n"
                f"请返回包含 runtime_contract、prompt_contract、tooling_contract 的 JSON。"
            )
            result = await self._call_nanobot(
                user_message=prompt,
                thread_context={"stage": "build_draft"},
            )
            response_text = str(result.get("response", "") or "")
            try:
                contracts = json.loads(response_text)
                runtime_contract = contracts.get("runtime_contract", {})
                prompt_contract = contracts.get("prompt_contract", {})
                tooling_contract = contracts.get("tooling_contract", {})
            except json.JSONDecodeError:
                runtime_contract = {}
                prompt_contract = {}
                tooling_contract = {}
        except Exception as e:
            logger.warning("[NanobotBuilder] 构建草案失败: %s", e)
            runtime_contract = {}
            prompt_contract = {}
            tooling_contract = {}

        return AgentBuilderDraft(
            agent_id=agent_id,
            agent_name=agent_name,
            description=description,
            runtime_contract={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "description": description,
                "output_field": runtime_contract.get("output_field", "analysis_report"),
                "workflow_stage": runtime_contract.get("workflow_stage", "analyst"),
                "report_label": runtime_contract.get("report_label", f"【{agent_name}】"),
                "node_name": runtime_contract.get("node_name", agent_name),
                "execution_order": runtime_contract.get("execution_order", 50),
                "show_in_reports": runtime_contract.get("show_in_reports", True),
                "category": runtime_contract.get("category", "analyst"),
                "callable_surfaces": runtime_contract.get("callable_surfaces", ["assistant", "workflow", "agent_workshop"]),
            },
            prompt_contract={
                "agent_type": "universal",
                "agent_name": agent_id,
                "template_name": prompt_contract.get("template_name", f"{agent_name} 默认模板"),
                "status": prompt_contract.get("status", "draft"),
                "must_match_universal_agent": True,
            },
            tooling_contract={
                "required_tools": tooling_contract.get("required_tools", tooling_plan.get("required_tools", []) if tooling_plan else []),
                "default_tools": tooling_contract.get("default_tools", tooling_plan.get("default_tools", []) if tooling_plan else []),
                "missing_capabilities": tooling_contract.get("missing_capabilities", tooling_plan.get("missing_capabilities", []) if tooling_plan else []),
            },
            primary_goal=description,
            domain=spec.get("domain", "stock_analysis"),
            outputs=spec.get("outputs", ["analysis_report"]),
            non_goals=spec.get("non_goals", []),
            preferred_methods=spec.get("preferred_methods", []),
            constraints=spec.get("constraints", []),
            target_users=spec.get("target_users", []),
            tool_ids=tooling_plan.get("required_tools", []) if tooling_plan else [],
        )
