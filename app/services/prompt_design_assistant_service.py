"""
Prompt 设计助手服务 — Phase 3

通过自然语言对话优化 Agent 的 Prompt（基础模板 + 注入策略）。
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db
from app.models.prompt_template import PromptTemplateCreate, PromptTemplateUpdate, TemplateContent
from app.models.user_template_config import UserTemplateConfigCreate, UserTemplateConfigUpdate
from app.services.prompt_assembly_service import get_prompt_assembly_service
from app.services.prompt_injection_policy_service import PromptInjectionPolicyService
from app.services.prompt_template_service import PromptTemplateService
from app.services.user_template_config_service import UserTemplateConfigService
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
        self._template_service = PromptTemplateService(db=db)
        self._user_template_config_service = UserTemplateConfigService(db=db)

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
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """收集当前模板、策略和组装后的 Prompt"""
        template = self._template_client.get_effective_template(
            agent_type,
            agent_name,
            user_id=user_id,
            workflow_id=workflow_id,
            node_id=node_id,
        ) or {}
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
            workflow_id=workflow_id,
            node_id=node_id,
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
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
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
            user_id=user_id,
            workflow_id=workflow_id,
            node_id=node_id,
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

        # 记录 token 使用
        try:
            from app.services.usage_statistics_service import usage_statistics_service
            await usage_statistics_service.record_llm_usage(
                response=resp,
                session_id=session_id,
                analysis_type="prompt_design",
            )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")

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
                    "analysis_type": analysis_type,
                    "industry": industry,
                    "stock_symbol": stock_symbol,
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                    "messages": messages,
                    "last_suggested_changes": suggested_changes,
                    "review_status": "draft",
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

    def _normalize_template_content(self, template: Optional[Dict[str, Any]]) -> Dict[str, str]:
        fields = (
            "system_prompt",
            "user_prompt",
            "tool_guidance",
            "analysis_requirements",
            "output_format",
            "constraints",
        )
        source = template or {}
        return {field: str(source.get(field) or "") for field in fields}

    def _merge_template_content(
        self,
        base_content: Dict[str, str],
        proposed_template: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        merged = dict(base_content)
        for key, value in (proposed_template or {}).items():
            if key in merged and value is not None:
                merged[key] = str(value)
        return merged

    def _normalize_policy_changes(
        self,
        proposed_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}
        for scope, changes in (proposed_policy or {}).items():
            if scope not in {"general", "industry", "stock"}:
                continue
            if isinstance(changes, dict):
                normalized[scope] = changes
        return normalized

    def _snapshot_policy(self, policy: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not policy:
            return None
        return {
            "id": policy.get("id"),
            "agent_type": policy.get("agent_type"),
            "agent_name": policy.get("agent_name"),
            "scope": policy.get("scope"),
            "enabled": policy.get("enabled", True),
            "injection_mode": policy.get("injection_mode", "summary"),
            "inherit_industry_for_stock": policy.get("inherit_industry_for_stock", True),
            "include_capability_block": policy.get("include_capability_block", True),
            "include_external_gap_notice": policy.get("include_external_gap_notice", True),
            "include_comparable_companies": policy.get("include_comparable_companies", True),
            "inject_position": policy.get("inject_position", "analysis_requirements"),
        }

    def _build_diff_summary(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
        proposed_template: Optional[Dict[str, str]] = None,
        proposed_policy: Optional[Dict[str, Any]] = None,
    ) -> str:
        changed_fields = [key for key in (proposed_template or {}).keys() if key in before.get("template", {})]
        changed_scopes = [scope for scope in self._normalize_policy_changes(proposed_policy).keys()]
        lines = []
        if changed_fields:
            lines.append(f"模板字段变更: {', '.join(changed_fields)}")
        if changed_scopes:
            lines.append(f"策略场景变更: {', '.join(changed_scopes)}")
        before_len = len(before.get("assembled") or "")
        after_len = len(after.get("assembled") or "")
        if before_len != after_len:
            lines.append(f"组装后 Prompt 长度: {before_len} -> {after_len}")
        return "；".join(lines) if lines else "没有检测到可预览的结构化变更"

    def _find_unresolved_placeholders(self, text: str) -> List[str]:
        tokens = set()
        for match in re.findall(r"\{\{[^{}]+\}\}", text or ""):
            tokens.add(match)
        for match in re.findall(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", text or ""):
            tokens.add(match)
        return sorted(tokens)

    def _validate_applied_changes(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
        proposed_template: Optional[Dict[str, str]] = None,
        proposed_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        before_text = before.get("assembled") or ""
        after_text = after.get("assembled") or ""
        changed = before_text != after_text
        unresolved = self._find_unresolved_placeholders(after_text)
        changed_fields = [
            key for key, value in (proposed_template or {}).items()
            if after.get("template", {}).get(key) == str(value)
        ]
        policy_scopes = list(self._normalize_policy_changes(proposed_policy).keys())
        checks = {
            "prompt_changed": changed,
            "template_fields_applied": len(changed_fields) == len((proposed_template or {}).keys()),
            "policy_scopes_recorded": len(policy_scopes),
            "unresolved_placeholders": unresolved,
            "after_prompt_length": len(after_text),
            "before_prompt_length": len(before_text),
        }
        passed = (changed or bool(policy_scopes)) and not unresolved
        summary_parts = []
        if changed:
            summary_parts.append("组装后 Prompt 已变化")
        if changed_fields:
            summary_parts.append(f"模板字段已落地: {', '.join(changed_fields)}")
        if policy_scopes:
            summary_parts.append(f"策略场景已记录: {', '.join(policy_scopes)}")
        if unresolved:
            summary_parts.append(f"存在未替换占位符: {', '.join(unresolved[:5])}")
        return {
            "passed": passed,
            "summary": "；".join(summary_parts) if summary_parts else "未检测到有效变更",
            "checks": checks,
        }

    async def get_diff(
        self,
        agent_type: str,
        agent_name: str,
        proposed_template: Optional[Dict[str, str]] = None,
        proposed_policy: Optional[Dict[str, Any]] = None,
        analysis_type: str = "industry",
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
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
        template = self._template_client.get_effective_template(
            agent_type,
            agent_name,
            user_id=user_id,
            workflow_id=workflow_id,
            node_id=node_id,
        ) or {}
        normalized_template = self._normalize_template_content(template)
        before_assembled = self._assembly_service.assemble_prompt(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type=analysis_type,
            industry=industry or ("白酒" if analysis_type in ("industry", "stock") else None),
            stock_symbol=stock_symbol,
            include_capability=True,
            workflow_id=workflow_id,
            node_id=node_id,
        )

        before = {
            "template": normalized_template,
            "assembled": before_assembled.get("final_prompt", ""),
        }

        merged_template = self._merge_template_content(normalized_template, proposed_template)
        normalized_policy = self._normalize_policy_changes(proposed_policy)
        after_assembled = self._assembly_service.assemble_prompt(
            agent_type=agent_type,
            agent_name=agent_name,
            analysis_type=analysis_type,
            industry=industry or ("白酒" if analysis_type in ("industry", "stock") else None),
            stock_symbol=stock_symbol,
            include_capability=True,
            workflow_id=workflow_id,
            node_id=node_id,
            template_override=merged_template,
            policy_overrides=normalized_policy,
        )
        after = {
            "template": merged_template,
            "assembled": after_assembled.get("final_prompt", ""),
        }

        return {
            "before": before,
            "after": after,
            "diff_summary": self._build_diff_summary(before, after, proposed_template, proposed_policy),
        }

    async def apply_changes(
        self,
        session_id: Optional[str],
        agent_type: str,
        agent_name: str,
        user_id: str,
        proposed_template: Optional[Dict[str, str]] = None,
        proposed_policy: Optional[Dict[str, Any]] = None,
        analysis_type: str = "industry",
        industry: Optional[str] = None,
        stock_symbol: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not proposed_template and not proposed_policy:
            raise ValueError("没有可应用的结构化修改")

        diff_result = await self.get_diff(
            agent_type=agent_type,
            agent_name=agent_name,
            proposed_template=proposed_template,
            proposed_policy=proposed_policy,
            analysis_type=analysis_type,
            industry=industry,
            stock_symbol=stock_symbol,
            user_id=user_id,
            workflow_id=workflow_id,
            node_id=node_id,
        )

        current_template = self._template_client.get_effective_template(
            agent_type,
            agent_name,
            user_id=user_id,
            workflow_id=workflow_id,
            node_id=node_id,
        ) or {}
        current_template_id = str(current_template.get("template_id") or "").strip() or None
        current_template_doc = await self._template_service.get_template(current_template_id) if current_template_id else None
        merged_content = self._merge_template_content(self._normalize_template_content(current_template), proposed_template)
        previous_active_config = None
        if not workflow_id and not node_id:
            previous_active_config = await self._user_template_config_service.get_active_config(
                user_id,
                agent_type,
                agent_name,
                None,
            )
        previous_policy_snapshots: Dict[str, Optional[Dict[str, Any]]] = {}
        for scope in self._normalize_policy_changes(proposed_policy).keys():
            previous_policy_snapshots[scope] = self._snapshot_policy(
                await self._policy_service.get_policy_by_agent_scope(agent_type, agent_name, scope)
            )

        applied_template = None
        template_action = "skipped"

        if proposed_template:
            if current_template_doc and not current_template_doc.is_system and str(current_template_doc.created_by) == str(user_id):
                applied_template = await self._template_service.update_template(
                    str(current_template_doc.id),
                    PromptTemplateUpdate(
                        content=TemplateContent(**merged_content),
                        change_description="Prompt 设计助手应用修改",
                    ),
                    user_id=user_id,
                )
                template_action = "updated"
            else:
                template_name = f"{agent_name} 智能优化 {datetime.now().strftime('%m-%d %H:%M')}"
                applied_template = await self._template_service.create_template(
                    PromptTemplateCreate(
                        agent_type=agent_type,
                        agent_name=agent_name,
                        template_name=template_name,
                        workflow_id=workflow_id,
                        node_id=node_id,
                        preference_type=(getattr(current_template_doc, "preference_type", None) if current_template_doc else None),
                        content=TemplateContent(**merged_content),
                        remark="由 Prompt 设计助手自动生成",
                        status="active",
                    ),
                    user_id=user_id,
                    base_template_id=current_template_id,
                    base_version=(current_template_doc.version if current_template_doc else None),
                )
                template_action = "created"

            if applied_template and not workflow_id and not node_id:
                active_config = await self._user_template_config_service.get_active_config(
                    user_id,
                    agent_type,
                    agent_name,
                    None,
                )
                if active_config:
                    await self._user_template_config_service.update_config(
                        str(active_config.id),
                        UserTemplateConfigUpdate(template_id=str(applied_template.id), is_active=True),
                    )
                else:
                    await self._user_template_config_service.create_config(
                        user_id,
                        UserTemplateConfigCreate(
                            agent_type=agent_type,
                            agent_name=agent_name,
                            template_id=str(applied_template.id),
                        ),
                    )

        applied_policies: List[Dict[str, Any]] = []
        applied_policy_meta: Dict[str, Dict[str, Any]] = {}
        for scope, changes in self._normalize_policy_changes(proposed_policy).items():
            existing = await self._policy_service.get_policy_by_agent_scope(agent_type, agent_name, scope)
            if existing:
                policy = await self._policy_service.update_policy(existing["id"], changes)
                applied_policy_meta[scope] = {"action": "updated", "policy_id": existing["id"]}
            else:
                policy = await self._policy_service.create_policy({
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "scope": scope,
                    **changes,
                })
                applied_policy_meta[scope] = {"action": "created", "policy_id": (policy or {}).get("id")}
            if policy:
                applied_policies.append(policy)

        validation_result = self._validate_applied_changes(
            diff_result["before"],
            diff_result["after"],
            proposed_template,
            proposed_policy,
        )

        if session_id:
            await self._get_db()[COLLECTION].update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "last_applied_changes": {
                            "template_changes": proposed_template or {},
                            "policy_changes": proposed_policy or {},
                        },
                        "applied_by": user_id,
                        "applied_at": datetime.now(timezone.utc),
                        "applied_template_id": str(applied_template.id) if applied_template else None,
                        "applied_policy_ids": [item.get("id") for item in applied_policies],
                        "review_status": "applied",
                        "validation_result": validation_result,
                        "rollback_payload": {
                            "agent_type": agent_type,
                            "agent_name": agent_name,
                            "analysis_type": analysis_type,
                            "industry": industry,
                            "stock_symbol": stock_symbol,
                            "workflow_id": workflow_id,
                            "node_id": node_id,
                            "template_action": template_action,
                            "previous_template": {
                                "template_id": current_template_id,
                                "content": self._normalize_template_content(current_template),
                                "version": getattr(current_template_doc, "version", None) if current_template_doc else None,
                                "status": getattr(current_template_doc, "status", None) if current_template_doc else None,
                            } if current_template_id else None,
                            "previous_active_config": {
                                "config_id": str(previous_active_config.id),
                                "template_id": str(previous_active_config.template_id),
                            } if previous_active_config else None,
                            "applied_template": {
                                "template_id": str(applied_template.id),
                                "version": applied_template.version,
                            } if applied_template else None,
                            "previous_policies": previous_policy_snapshots,
                            "applied_policies": applied_policy_meta,
                        },
                    }
                },
            )

        return {
            "applied": True,
            "review_status": "applied",
            "template_action": template_action,
            "template": {
                "template_id": str(applied_template.id),
                "template_name": applied_template.template_name,
                "version": applied_template.version,
            } if applied_template else None,
            "policies": applied_policies,
            "validation_result": validation_result,
            "diff": diff_result,
        }

    async def rollback_changes(
        self,
        session_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        db = self._get_db()
        session = await db[COLLECTION].find_one({"session_id": session_id})
        if not session:
            raise ValueError(f"会话不存在: {session_id}")
        rollback_payload = session.get("rollback_payload") or {}
        if not rollback_payload:
            raise ValueError("当前会话没有可回退的应用记录")
        if session.get("review_status") == "rolled_back":
            raise ValueError("当前会话最近一次应用已经回退")

        agent_type = rollback_payload.get("agent_type") or session.get("agent_type")
        agent_name = rollback_payload.get("agent_name") or session.get("agent_name")
        workflow_id = rollback_payload.get("workflow_id")
        node_id = rollback_payload.get("node_id")
        template_action = rollback_payload.get("template_action") or "skipped"
        previous_template = rollback_payload.get("previous_template") or {}
        applied_template = rollback_payload.get("applied_template") or {}
        previous_active_config = rollback_payload.get("previous_active_config") or {}

        rollback_actions: List[str] = []
        applied_template_id = (applied_template.get("template_id") or "").strip()
        previous_template_id = (previous_template.get("template_id") or "").strip()

        if template_action == "updated" and applied_template_id and previous_template.get("content"):
            updated = await self._template_service.update_template(
                applied_template_id,
                PromptTemplateUpdate(
                    content=TemplateContent(**previous_template["content"]),
                    change_description="Prompt 设计助手回退到应用前版本",
                ),
                user_id=user_id,
            )
            if updated:
                rollback_actions.append("已恢复被更新模板的上一个内容版本")
        elif template_action == "created" and applied_template_id:
            created_template_doc = await self._template_service.get_template(applied_template_id)
            if created_template_doc:
                await self._template_service.update_template(
                    applied_template_id,
                    PromptTemplateUpdate(
                        status="draft",
                        change_description="Prompt 设计助手回退时停用新建模板",
                    ),
                    user_id=user_id,
                )
                rollback_actions.append("已停用本次新建的覆盖模板")

            if workflow_id or node_id:
                if previous_template_id:
                    rollback_actions.append("流程/节点模板已回退到原有活动模板")
            else:
                current_active_config = await self._user_template_config_service.get_active_config(
                    user_id,
                    agent_type,
                    agent_name,
                    None,
                )
                if previous_active_config.get("config_id"):
                    if current_active_config and str(current_active_config.id) == str(previous_active_config.get("config_id")):
                        await self._user_template_config_service.update_config(
                            str(current_active_config.id),
                            UserTemplateConfigUpdate(
                                template_id=str(previous_active_config.get("template_id")),
                                is_active=True,
                            ),
                        )
                    rollback_actions.append("已恢复应用前的用户模板配置")
                elif current_active_config and str(current_active_config.template_id) == applied_template_id:
                    await self._user_template_config_service.update_config(
                        str(current_active_config.id),
                        UserTemplateConfigUpdate(is_active=False),
                    )
                    rollback_actions.append("已停用本次创建的用户模板配置，恢复系统默认模板")

        for scope, meta in (rollback_payload.get("applied_policies") or {}).items():
            previous_policy = (rollback_payload.get("previous_policies") or {}).get(scope)
            policy_id = meta.get("policy_id")
            if meta.get("action") == "created" and policy_id and not previous_policy:
                deleted = await self._policy_service.delete_policy(policy_id)
                if deleted:
                    rollback_actions.append(f"已删除场景 {scope} 下本次新建的注入策略")
            elif policy_id and previous_policy:
                restored = await self._policy_service.update_policy(policy_id, previous_policy)
                if restored:
                    rollback_actions.append(f"已恢复场景 {scope} 的原始注入策略")

        await db[COLLECTION].update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "review_status": "rolled_back",
                    "rolled_back_at": datetime.now(timezone.utc),
                    "rolled_back_by": user_id,
                    "rollback_summary": rollback_actions,
                }
            },
        )

        return {
            "rolled_back": True,
            "review_status": "rolled_back",
            "summary": rollback_actions or ["未检测到需要回退的内容"],
        }
