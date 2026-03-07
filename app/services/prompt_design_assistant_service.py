"""
Prompt 设计助手服务 — Phase 3

通过自然语言对话优化 Agent 的 Prompt（基础模板 + 注入策略）。
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db
from app.services.prompt_assembly_service import get_prompt_assembly_service
from app.services.prompt_injection_policy_service import PromptInjectionPolicyService
from tradingagents.utils.template_client import get_template_client

logger = logging.getLogger(__name__)

COLLECTION = "prompt_design_sessions"
_LLM_TIMEOUT = 120


class PromptDesignAssistantService:
    """Prompt 设计助手 — 对话式优化模板与策略"""

    def __init__(self, db=None):
        self._db = db
        self._llm_client = None
        self._template_client = get_template_client()
        self._assembly_service = get_prompt_assembly_service()
        self._policy_service = PromptInjectionPolicyService()

    def _get_db(self):
        if self._db is not None:
            return self._db
        return get_mongo_db()

    async def _ensure_llm_client(self):
        """确保 LLM 客户端已初始化"""
        if self._llm_client is not None:
            return self._llm_client
        try:
            from app.services.intelligent_assistant_service import get_reasoning_llm_config
            from core.llm import UnifiedLLMClient

            db = self._get_db()
            config = await get_reasoning_llm_config(db)
            if config:
                config.timeout = max(getattr(config, "timeout", 60), _LLM_TIMEOUT)
                self._llm_client = UnifiedLLMClient.from_config(config)
                logger.info(f"[PromptDesign] LLM 初始化: provider={config.provider}, model={config.model}")
                return self._llm_client
        except Exception as e:
            logger.warning(f"[PromptDesign] 获取推理模型失败: {e}")
        from core.llm import UnifiedLLMClient
        self._llm_client = UnifiedLLMClient.from_provider("deepseek", timeout=_LLM_TIMEOUT)
        return self._llm_client

    def _collect_context(
        self,
        agent_type: str,
        agent_name: str,
        analysis_type: str = "industry",
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """收集当前模板、策略和组装后的 Prompt"""
        template = self._template_client.get_effective_template(agent_type, agent_name) or {}
        policies = []
        for scope in ("general", "industry", "stock"):
            p = self._policy_service.get_policy_by_agent_scope_sync(agent_type, agent_name, scope)
            if p:
                policies.append(p)

        assembled = self._assembly_service.assemble_prompt(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type=analysis_type,
            industry=industry or "白酒",
            stock_symbol=stock_symbol,
            include_capability=True,
        )

        return {
            "template": {
                "template_id": template.get("template_id", ""),
                "system_prompt": (template.get("system_prompt") or "")[:500],
                "analysis_requirements": (template.get("analysis_requirements") or "")[:800],
                "constraints": (template.get("constraints") or "")[:500],
            },
            "policies": [
                {
                    "scope": p.get("scope"),
                    "injection_mode": p.get("injection_mode"),
                    "inherit_industry_for_stock": p.get("inherit_industry_for_stock"),
                    "include_capability_block": p.get("include_capability_block"),
                }
                for p in policies
            ],
            "assembled_preview": (assembled.get("final_prompt") or "")[:1500],
        }

    async def chat(
        self,
        session_id: str,
        message: str,
        agent_type: str,
        agent_name: str,
        analysis_type: str = "industry",
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        对话式 Prompt 优化

        Args:
            session_id: 会话 ID（新建时传空，返回新 session_id）
            message: 用户消息
            agent_type: Agent 类型
            agent_name: Agent 名称
            analysis_type: 分析场景
            industry: 行业（用于预览）
            stock_symbol: 个股（用于预览）

        Returns:
            {
                "session_id": str,
                "ai_message": str,
                "suggested_changes": Optional[Dict],  # 结构化建议
            }
        """
        db = self._get_db()

        # 加载或创建会话
        if session_id:
            doc = await db[COLLECTION].find_one({"session_id": session_id})
            if not doc:
                raise ValueError(f"会话不存在: {session_id}")
            messages = doc.get("messages", [])
        else:
            session_id = str(uuid.uuid4())
            messages = []

        messages.append({"role": "user", "content": message})

        # 收集上下文
        context = self._collect_context(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type=analysis_type,
            industry=industry,
            stock_symbol=stock_symbol,
        )

        # 构建系统提示
        system_prompt = """你是 Prompt 设计助手，帮助用户优化 TradingAgents 中 Agent 的提示词。

当前 Agent: {agent_type} / {agent_name}
当前场景: {analysis_type}

## 当前配置摘要

### 基础模板
- system_prompt: (前500字)
- analysis_requirements: (前800字)
- constraints: (前500字)

### 注入策略
{policy_summary}

### 组装后 Prompt 预览（前1500字）
{assembled_preview}

## 你的任务
1. 理解用户意图
2. 给出具体、可落地的修改建议
3. 若用户要求明确，可输出 JSON 格式的结构化建议，格式如下：
```json
{{
  "template_changes": {{
    "analysis_requirements": "修改后的完整内容",
    "constraints": "修改后的完整内容"
  }},
  "policy_changes": {{
    "industry": {{ "injection_mode": "full" }},
    "stock": {{ "inherit_industry_for_stock": false }}
  }}
}}
```
仅当用户明确要求修改且你能给出具体内容时，才输出上述 JSON。否则输出自然语言建议。
""".format(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type=analysis_type,
            policy_summary=json.dumps(context["policies"], ensure_ascii=False, indent=2),
            assembled_preview=context["assembled_preview"],
        )

        # 调用 LLM（转换为 Message 格式）
        from core.llm import Message, MessageRole
        llm_messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content="当前模板的 analysis_requirements 前800字：\n" + context["template"]["analysis_requirements"]),
            Message(role=MessageRole.ASSISTANT, content="我已了解当前配置，请继续描述你的优化需求。"),
        ]
        for m in messages[-6:]:
            role = MessageRole.USER if m["role"] == "user" else MessageRole.ASSISTANT
            llm_messages.append(Message(role=role, content=m["content"]))

        client = await self._ensure_llm_client()
        resp = await client.achat(llm_messages)
        ai_content = (resp.content or "").strip()

        # 尝试解析 JSON 建议
        suggested_changes = None
        if "```json" in ai_content:
            try:
                start = ai_content.find("```json") + 7
                end = ai_content.find("```", start)
                if end > start:
                    json_str = ai_content[start:end].strip()
                    suggested_changes = json.loads(json_str)
            except json.JSONDecodeError:
                pass

        messages.append({"role": "assistant", "content": ai_content})

        # 持久化
        await db[COLLECTION].update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "messages": messages,
                    "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            },
            upsert=True,
        )

        return {
            "session_id": session_id,
            "ai_message": ai_content,
            "suggested_changes": suggested_changes,
        }

    async def get_diff(
        self,
        agent_type: str,
        agent_name: str,
        proposed_template: Optional[Dict[str, str]] = None,
        proposed_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        获取修改前后对比

        Returns:
            {
                "before": { "template": {...}, "assembled": str },
                "after": { "template": {...}, "assembled": str },
                "diff_summary": str,
            }
        """
        # 当前状态
        template = self._template_client.get_effective_template(agent_type, agent_name) or {}
        before_assembled = self._assembly_service.assemble_prompt(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type="industry",
            industry="白酒",
            include_capability=True,
        )

        before = {
            "template": {
                "analysis_requirements": template.get("analysis_requirements", ""),
                "constraints": template.get("constraints", ""),
            },
            "assembled": before_assembled.get("final_prompt", ""),
        }

        # 暂不实现 apply 逻辑，diff 仅返回 before
        after = before.copy()
        if proposed_template:
            after["template"] = {**before["template"], **proposed_template}

        return {
            "before": before,
            "after": after,
            "diff_summary": "对比预览（apply 功能待完善）",
        }
