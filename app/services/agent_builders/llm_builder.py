"""
LLM Builder Provider

回退/测试实现，直接调用 LLM 进行需求澄清、缺口分析和工具规划。
用于没有 Embedded Nanobot 或 Hermes 可用时的降级方案。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.agent_builders.base import AgentBuilderDraft, AgentBuilderProvider

logger = logging.getLogger("webapi")


class LLMBuilderProvider(AgentBuilderProvider):
    """基于 LLM 直连的构建器实现（回退/测试用）"""

    def __init__(self, llm_client=None):
        self._llm_client = llm_client

    @property
    def provider_name(self) -> str:
        return "llm"

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        if self._llm_client is None:
            raise RuntimeError("LLMBuilderProvider 未配置 LLM 客户端")
        if hasattr(self._llm_client, "achat"):
            response = await self._llm_client.achat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
            return str(response or "")
        raise RuntimeError("LLM 客户端不支持 achat 方法")

    async def clarify_requirements(
        self,
        *,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        system_prompt = """你是一个 Agent 需求分析师。分析用户输入，返回 JSON：
{
  "agent_name": "Agent 名称",
  "primary_goal": "单一职责描述",
  "domain": "stock_analysis",
  "outputs": ["输出字段列表"],
  "non_goals": ["不做什么"],
  "preferred_methods": ["推荐方法"],
  "constraints": ["约束条件"],
  "target_users": ["目标用户"],
  "pending_questions": ["待澄清问题"],
  "completeness_score": 0.0-1.0
}"""
        user_prompt = f"用户需求：{user_message}"
        if current_spec:
            user_prompt += f"\n当前规格：{json.dumps(current_spec, ensure_ascii=False)}"

        try:
            response = await self._call_llm(system_prompt, user_prompt)
            return json.loads(response)
        except Exception as e:
            logger.warning("[LLMBuilder] 需求澄清失败: %s", e)
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
        system_prompt = """分析 Agent 规格与可用资源的缺口，返回 JSON：
{
  "data_gaps": ["数据缺口"],
  "tool_gaps": ["工具缺口"],
  "capability_gaps": ["能力缺口"],
  "severity": "low|medium|high",
  "recommendations": ["建议"]
}"""
        user_prompt = f"规格：{json.dumps(spec, ensure_ascii=False)}"
        if available_tools:
            user_prompt += f"\n可用工具：{json.dumps(available_tools, ensure_ascii=False)}"

        try:
            response = await self._call_llm(system_prompt, user_prompt)
            return json.loads(response)
        except Exception as e:
            logger.warning("[LLMBuilder] 缺口分析失败: %s", e)
            return {"data_gaps": [], "tool_gaps": [], "capability_gaps": [], "severity": "low"}

    async def plan_tooling(
        self,
        *,
        spec: Dict[str, Any],
        gap_report: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        system_prompt = """规划 Agent 工具方案，返回 JSON：
{
  "required_tools": ["tool_id1", "tool_id2"],
  "default_tools": ["tool_id1"],
  "missing_capabilities": ["缺失能力"],
  "rationale": "规划理由"
}"""
        user_prompt = f"规格：{json.dumps(spec, ensure_ascii=False)}"
        if gap_report:
            user_prompt += f"\n缺口报告：{json.dumps(gap_report, ensure_ascii=False)}"

        try:
            response = await self._call_llm(system_prompt, user_prompt)
            return json.loads(response)
        except Exception as e:
            logger.warning("[LLMBuilder] 工具规划失败: %s", e)
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

        return AgentBuilderDraft(
            agent_id=agent_id,
            agent_name=agent_name,
            description=description,
            runtime_contract={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "description": description,
                "output_field": "analysis_report",
                "workflow_stage": "analyst",
                "report_label": f"【{agent_name}】",
                "node_name": agent_name,
                "execution_order": 50,
                "show_in_reports": True,
                "category": "analyst",
                "callable_surfaces": ["assistant", "workflow", "agent_workshop"],
            },
            prompt_contract={
                "agent_type": "universal",
                "agent_name": agent_id,
                "template_name": f"{agent_name} 默认模板",
                "status": "draft",
                "must_match_universal_agent": True,
            },
            tooling_contract={
                "required_tools": tooling_plan.get("required_tools", []) if tooling_plan else [],
                "default_tools": tooling_plan.get("default_tools", []) if tooling_plan else [],
                "missing_capabilities": tooling_plan.get("missing_capabilities", []) if tooling_plan else [],
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
