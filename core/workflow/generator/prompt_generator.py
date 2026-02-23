"""
提示词生成器 — 为工作流中的 Agent 生成专属提示词

根据蓝图中的缺口分析结果 (gap_analysis.agent_reshaping)，
为需要定制的 Agent 生成工作流专属提示词，保存到 prompt_templates 集合。

加载机制（已有，无需修改）:
    Debug模板 > 工作流专属模板(workflow_id) > 用户模板 > 系统默认模板

参考: docs/design/v3.0/ai-workflow-generation.md §4.3
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.llm import UnifiedLLMClient, Message
from .workflow_spec import AgentReshapingPlan, WorkflowBlueprint

logger = logging.getLogger(__name__)

# Agent category → prompt_templates 的 agent_type 映射
_CATEGORY_TO_AGENT_TYPE = {
    "analyst": "analysts",
    "researcher": "researchers",
    "trader": "trader",
    "risk": "risk",
    "manager": "managers",
    "post_processor": "post_processor",
}

# 提示词扩展 prompt — 用于将草案扩展为完整的 TemplateContent
EXPAND_PROMPT = """\
你是一个专业的提示词工程师。请根据以下信息，为 Agent 生成完整的工作流专属提示词。

## Agent 信息
- Agent ID: {agent_id}
- 原始角色: {original_role}
- 新角色（本工作流）: {new_role}
- 工作流名称: {workflow_name}
- 工作流描述: {workflow_description}

## 现有草案
{draft_json}

## 输出要求

请输出一个完整的提示词配置，包含以下 6 个字段。如果草案中已有某字段的内容，在其基础上完善；如果没有，请根据角色需求生成。

1. **system_prompt** — 系统提示词，定义 AI 角色和核心行为准则（200-500字）
2. **user_prompt** — 用户提示词模板，使用 {{stock_symbol}} 等变量（可留空）
3. **tool_guidance** — 工具使用指导，说明优先使用哪些工具、参数注意事项（100-300字）
4. **analysis_requirements** — 分析要求，列出需要关注的具体维度（100-300字）
5. **output_format** — 输出格式模板，用 markdown 定义报告结构
6. **constraints** — 约束条件，限制范围和注意事项（50-200字）

请严格按照以下 JSON 格式输出（不要包含其他文本）：
{{
    "system_prompt": "...",
    "user_prompt": "",
    "tool_guidance": "...",
    "analysis_requirements": "...",
    "output_format": "...",
    "constraints": "..."
}}
"""


class PromptGenerator:
    """
    提示词生成器

    根据蓝图中的 gap_analysis.agent_reshaping，
    为需要定制提示词的 Agent 批量生成工作流专属提示词。
    """

    def __init__(self, db, llm_client: Optional[UnifiedLLMClient] = None):
        """
        Args:
            db: MongoDB 数据库实例（同步或异步）
            llm_client: LLM 客户端（用于扩展提示词草案）
        """
        self._db = db
        self._llm_client = llm_client

    async def generate_prompts(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
    ) -> List[str]:
        """
        为需要定制提示词的 Agent 批量生成工作流专属提示词

        Args:
            workflow_id: 工作流 ID
            blueprint: AI 生成的蓝图

        Returns:
            创建成功的 prompt_template ID 列表
        """
        if not blueprint.gap_analysis:
            logger.info("[PromptGenerator] 无缺口分析，跳过提示词生成")
            return []

        reshaping_list = blueprint.gap_analysis.agent_reshaping
        if not reshaping_list:
            logger.info("[PromptGenerator] 无需定制提示词的 Agent")
            return []

        created_ids: List[str] = []
        for plan in reshaping_list:
            try:
                template_id = await self._generate_one_prompt(
                    workflow_id=workflow_id,
                    plan=plan,
                    blueprint=blueprint,
                )
                if template_id:
                    created_ids.append(template_id)
                    logger.info(
                        f"[PromptGenerator] ✅ {plan.agent_id} 提示词已创建: {template_id}"
                    )
            except Exception as e:
                logger.error(
                    f"[PromptGenerator] ❌ {plan.agent_id} 提示词生成失败: {e}",
                    exc_info=True,
                )

        # 更新蓝图创建进度
        blueprint.creation_progress["prompts_completed"] = len(created_ids)

        return created_ids

    async def _generate_one_prompt(
        self,
        workflow_id: str,
        plan: AgentReshapingPlan,
        blueprint: WorkflowBlueprint,
    ) -> Optional[str]:
        """
        为单个 Agent 生成工作流专属提示词

        如果蓝图草案中 prompt_changes 已经有完整内容（≥4 个字段），直接使用；
        否则调用 LLM 扩展为完整的 TemplateContent。
        """
        import json

        # 检查草案是否足够完整（至少有 system_prompt + tool_guidance + analysis_requirements + output_format）
        draft = plan.prompt_changes
        required_keys = {"system_prompt", "tool_guidance", "analysis_requirements", "output_format"}
        has_enough = required_keys.issubset(draft.keys()) and all(
            len(draft.get(k, "")) > 20 for k in required_keys
        )

        if has_enough:
            content = self._normalize_content(draft)
        elif self._llm_client:
            content = await self._expand_prompt_draft(plan, blueprint)
        else:
            # 没有 LLM 也没有完整草案，用草案原文兜底
            content = self._normalize_content(draft)

        if not content:
            return None

        # 查询 Agent 元数据以确定 agent_type
        agent_type = await self._resolve_agent_type(plan.agent_id)

        # 保存到 prompt_templates 集合
        template_doc = {
            "agent_type": agent_type,
            "agent_name": plan.agent_id,
            "template_name": plan.new_role or f"{plan.agent_id} - 工作流专属",
            "workflow_id": workflow_id,
            "preference_type": "workflow",
            "content": content,
            "remark": f"由 AI 工作流架构师自动生成 (workflow: {blueprint.name})",
            "is_system": False,
            "created_by": None,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "version": 1,
        }

        result = await self._db.prompt_templates.insert_one(template_doc)
        return str(result.inserted_id)

    async def _expand_prompt_draft(
        self,
        plan: AgentReshapingPlan,
        blueprint: WorkflowBlueprint,
    ) -> Optional[Dict[str, str]]:
        """调用 LLM 将草案扩展为完整的 TemplateContent"""
        import json as _json

        draft_json = _json.dumps(plan.prompt_changes, ensure_ascii=False, indent=2)
        prompt = EXPAND_PROMPT.format(
            agent_id=plan.agent_id,
            original_role=plan.original_role,
            new_role=plan.new_role,
            workflow_name=blueprint.name,
            workflow_description=blueprint.description,
            draft_json=draft_json,
        )

        messages = [
            Message(role="system", content="你是一个提示词工程师，请严格按 JSON 格式输出。"),
            Message(role="user", content=prompt),
        ]

        try:
            response = self._llm_client.chat(messages)
            raw = response.content or ""
            # 尝试提取 JSON
            from .workflow_planner import WorkflowPlanner
            data = WorkflowPlanner._try_parse_json(raw.strip())
            if data is None:
                # 尝试 ```json``` 代码块
                import re
                match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
                if match:
                    data = WorkflowPlanner._try_parse_json(match.group(1).strip())
            if data and isinstance(data, dict):
                return self._normalize_content(data)
        except Exception as e:
            logger.error(f"[PromptGenerator] LLM 扩展失败: {e}", exc_info=True)

        # 兜底: 用草案原文
        return self._normalize_content(plan.prompt_changes)

    @staticmethod
    def _normalize_content(data: Dict[str, str]) -> Dict[str, str]:
        """确保 content 包含 TemplateContent 所需的所有字段"""
        return {
            "system_prompt": data.get("system_prompt", ""),
            "user_prompt": data.get("user_prompt", ""),
            "tool_guidance": data.get("tool_guidance", ""),
            "analysis_requirements": data.get("analysis_requirements", ""),
            "output_format": data.get("output_format", ""),
            "constraints": data.get("constraints", ""),
        }

    async def _resolve_agent_type(self, agent_id: str) -> str:
        """根据 agent_id 确定 prompt_templates 中的 agent_type"""
        # 优先从数据库 agent_configs 查
        if self._db:
            try:
                agent_doc = await self._db.agent_configs.find_one({"agent_id": agent_id})
                if agent_doc and "category" in agent_doc:
                    cat = agent_doc["category"]
                    return _CATEGORY_TO_AGENT_TYPE.get(cat, cat)
            except Exception:
                pass

        # 回退: 从 BUILTIN_AGENTS 查
        try:
            from core.agents.config import BUILTIN_AGENTS
            meta = BUILTIN_AGENTS.get(agent_id)
            if meta:
                cat = meta.category if hasattr(meta, "category") else "analyst"
                cat_str = cat.value if hasattr(cat, "value") else str(cat)
                return _CATEGORY_TO_AGENT_TYPE.get(cat_str, cat_str)
        except Exception:
            pass

        # 最终兜底
        return "analysts"

