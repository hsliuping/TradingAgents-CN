"""
资源收集器 — 从系统中收集可用资源供 AI 规划使用

收集内容：
1. BUILTIN_AGENTS — 内置 Agent 列表（id, name, description, category, tools）
2. BUILTIN_TOOLS — 内置工具列表（id, name, description, category）
3. skills/external_skills — MongoDB 中的标准 Skill 和外部 Skill
4. agent_configs — MongoDB 中的 Agent 配置（可能包含用户自定义 Agent）
5. prompt_templates — 提示词模板摘要（用于理解 Agent 默认能力）

参考: docs/05-design/v3.0/ai-workflow-generation.md §4.1
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# 通用 Agent：无论什么流程都需要（报告生成、数据准备）
_UNIVERSAL_AGENT_IDS = {"report_generator_v2", "data_preparer_v2"}

# 相关性过滤：Agent 数上限（搜索 top-K 最相关的）
_MAX_RELEVANT_AGENTS = 15


class ResourceCollector:
    """
    资源收集器

    从代码配置和 MongoDB 收集所有可用资源，
    构建 LLM 可理解的上下文文本（控制在 ~4000-6000 tokens）。
    """

    def __init__(self, db=None):
        """
        Args:
            db: MongoDB 数据库实例（可选，不传则只使用内置配置）
        """
        self._db = db

    def set_database(self, db) -> None:
        self._db = db

    async def collect_all(
        self, user_query: Optional[str] = None,
        capability_index=None
    ) -> Dict[str, Any]:
        """
        收集所有可用资源

        Args:
            user_query: 用户的工作流需求描述，用于 Agent 相关性过滤。
                       传 None 则返回全部 Agent。
            capability_index: CapabilityIndexService 实例（可选）。
                             提供时启用向量语义搜索过滤 Agent。

        Returns:
            {
                "agents": [...],
                "tools": [...],
                "external_skills": [...],
                "prompt_summaries": [...],
                "node_types": [...],
                "context_text": "..."   # 汇总的文本描述
            }
        """
        agents = await self._collect_agents()

        # 🎯 向量语义搜索过滤：通过 CapabilityIndex 找到最相关的 Agent
        if user_query and capability_index and agents:
            agents = await self._filter_agents_via_capability_index(
                agents, user_query, capability_index
            )

        tools = self._collect_tools()
        skills = await self._collect_external_skills()
        prompt_summaries = await self._collect_prompt_summaries()
        node_types = self._get_node_types()

        context_text = self._build_context_text(
            agents, prompt_summaries, node_types
        )

        return {
            "agents": agents,
            "tools": tools,
            "external_skills": skills,
            "prompt_summaries": prompt_summaries,
            "node_types": node_types,
            "context_text": context_text,
        }

    async def _filter_agents_via_capability_index(
        self, agents: List[Dict[str, Any]], user_query: str,
        capability_index
    ) -> List[Dict[str, Any]]:
        """
        通过 CapabilityIndex 的向量语义搜索筛选最相关的 Agent

        规则：
        1. 用 user_query 搜索 source_type="agent" 的能力项
        2. source=database 的自定义 Agent 始终保留（用户显式创建的）
        3. 始终保留通用 Agent（report_generator_v2, data_preparer_v2）
        """
        # 分离内置和自定义 Agent
        builtin = [a for a in agents if a.get("source") != "database"]
        custom = [a for a in agents if a.get("source") == "database"]

        if not builtin:
            return custom  # 没有内置 Agent，直接返回自定义的

        try:
            hits = await capability_index.search_capabilities(
                query=user_query,
                top_k=max(_MAX_RELEVANT_AGENTS - len(custom), 5),
                source_types=["agent"],
            )
        except Exception as e:
            logger.warning(
                f"[ResourceCollector] CapabilityIndex Agent 搜索失败，回退到全部 Agent: {e}"
            )
            return agents

        if not hits:
            logger.info("[ResourceCollector] CapabilityIndex 未找到相关 Agent，使用全部")
            return agents

        # 构建搜索结果 ID 集合
        hit_ids = {h.capability.capability_id for h in hits}
        hit_scores = {h.capability.capability_id: h.score for h in hits}

        # 🔍 调试：打印 CapabilityIndex 搜索命中的 Agent
        logger.info(
            f"🔍 [ResourceCollector] CapabilityIndex 向量搜索结果 (top_k={max(_MAX_RELEVANT_AGENTS - len(custom), 5)}): "
            f"{[(cid, round(score, 3)) for cid, score in sorted(hit_scores.items(), key=lambda x: -x[1])]}"
        )

        # 始终加入通用 Agent
        hit_ids.update(_UNIVERSAL_AGENT_IDS)

        # 按 ID 匹配内置 Agent
        matched_builtin = [a for a in builtin if a["id"] in hit_ids]
        matched_ids = {a["id"] for a in matched_builtin}
        filtered_out = [a["id"] for a in builtin if a["id"] not in hit_ids]

        # 合并：自定义 Agent（全部保留） + 匹配到的内置 Agent
        result = custom + matched_builtin

        total_in = len(builtin) + len(custom)
        total_out = len(result)
        logger.info(
            f"🎯 [ResourceCollector] CapabilityIndex 向量过滤: "
            f"{total_in} → {total_out} Agent "
            f"(内置: {len(builtin)}→{len(matched_builtin)}, "
            f"自定义: {len(custom)} 全部保留, "
            f"查询='{user_query[:80]}')"
        )
        logger.info(
            f"   ✅ 保留的内置: {sorted(matched_ids)}"
        )
        if filtered_out and len(filtered_out) <= 30:
            logger.info(f"   ❌ 过滤掉的内置: {sorted(filtered_out)}")

        return result

    async def _collect_agents(self) -> List[Dict[str, Any]]:
        """收集可用的 Agent 列表（仅 MAINTANED 状态，过滤掉 DEPRECATED/UNMAINTAINED）"""
        agents = []

        # 1. 从内置配置收集（仅 MAINTAINED）
        try:
            from core.agents.config import BUILTIN_AGENTS, AgentMaintenanceStatus
            for agent_id, meta in BUILTIN_AGENTS.items():
                # 🛡️ 过滤掉已废弃的 Agent，防止 LLM 在过大的列表中迷失
                if meta.maintenance_status == AgentMaintenanceStatus.DEPRECATED:
                    continue
                if meta.maintenance_status == AgentMaintenanceStatus.UNMAINTAINED:
                    continue
                agents.append({
                    "id": meta.id,
                    "name": meta.name,
                    "description": meta.description,
                    "category": meta.category.value if hasattr(meta.category, 'value') else str(meta.category),
                    "default_tools": list(meta.default_tools),
                    "output_field": meta.output_field or "",
                    "report_label": meta.report_label or "",
                    "maintenance_status": meta.maintenance_status.value if hasattr(meta.maintenance_status, 'value') else str(meta.maintenance_status),
                    "source": "builtin",
                })
        except Exception as e:
            logger.warning(f"加载内置 Agent 失败: {e}")

        # 2. 从 MongoDB 补充（用户可能创建了自定义 Agent）
        if self._db is not None:
            try:
                builtin_ids = {a["id"] for a in agents}

                # 🛡️ 构建 v1→v2 阻止列表：过滤掉数据库中残留的旧版 v1 Agent
                #    例如 market_analyst (v1) 已有 market_analyst_v2 (v2) 替代
                v1_to_block: set = set()
                for builtin_id in builtin_ids:
                    if builtin_id.endswith("_v2"):
                        base = builtin_id[:-3]  # 去掉 _v2 后缀
                        if base not in builtin_ids:
                            v1_to_block.add(base)

                db_agents = self._db.agent_configs.find({"enabled": True})
                blocked_count = 0
                async for doc in db_agents:
                    aid = doc.get("agent_id", "")
                    if aid and aid not in builtin_ids:
                        # 过滤掉数据库中的旧版 v1 Agent（已有 v2 替代）
                        if aid in v1_to_block:
                            blocked_count += 1
                            logger.debug(f"🚫 [ResourceCollector] 过滤数据库旧版 Agent: {aid} (已有 v2)")
                            continue
                        agents.append({
                            "id": aid,
                            "name": doc.get("name", aid),
                            "description": doc.get("description", ""),
                            "category": doc.get("category", "custom"),
                            "default_tools": doc.get("default_tools", []),
                            "output_field": doc.get("output_field") or doc.get("result_field", ""),
                            "report_label": doc.get("report_label", ""),
                            "source": "database",
                        })
                if blocked_count > 0:
                    logger.info(
                        f"🛡️ [ResourceCollector] 过滤了 {blocked_count} 个数据库旧版 Agent"
                        f"（已有 v2 内置版本替代）"
                    )
            except Exception as e:
                logger.warning(f"从数据库加载 Agent 配置失败: {e}")

        return agents

    def _collect_tools(self) -> List[Dict[str, Any]]:
        """收集可用的工具列表"""
        tools = []
        try:
            from core.tools.config import BUILTIN_TOOLS
            for tool_id, meta in BUILTIN_TOOLS.items():
                tools.append({
                    "id": meta.id,
                    "name": meta.name,
                    "description": meta.description,
                    "category": meta.category.value if hasattr(meta.category, 'value') else str(meta.category),
                    "source": "builtin",
                })
        except Exception as e:
            logger.warning(f"加载内置工具失败: {e}")
        return tools

    async def _collect_external_skills(self) -> List[Dict[str, Any]]:
        """收集标准 Skill 和外部 Skill"""
        skills = []
        if self._db is None:
            return skills
        try:
            standard_docs = self._db.skills.find({"enabled": True})
            async for doc in standard_docs:
                name = doc.get("name", "")
                skills.append({
                    "id": name.replace("-", "_"),
                    "name": name,
                    "description": doc.get("description", ""),
                    "category": doc.get("category", "standard"),
                    "source": "standard_skill",
                })

            external_docs = self._db.external_skills.find({"status": "active"})
            async for doc in external_docs:
                skills.append({
                    "id": doc.get("tool_id", ""),
                    "name": doc.get("display_name") or doc.get("name", ""),
                    "description": doc.get("description", ""),
                    "category": doc.get("metadata", {}).get("category", "external"),
                    "source": "external_skill",
                })
        except Exception as e:
            logger.warning(f"从数据库加载 Skill 失败: {e}")
        return skills

    async def _collect_prompt_summaries(self) -> List[Dict[str, str]]:
        """
        收集提示词模板摘要

        获取每个 Agent 是否有自定义模板，并读取系统默认提示词的内容摘要，
        帮助 AI 基于实际提示词内容判断"复用 vs 优化"。
        """
        summaries = []
        if self._db is None:
            return summaries
        try:
            # 获取系统默认提示词的摘要（含 system_prompt 内容前 800 字）
            pipeline = [
                {"$match": {"status": "active", "is_system": True, "workflow_id": None}},
                {"$group": {
                    "_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"},
                    "template_names": {"$push": "$template_name"},
                    "has_workflow_specific": {
                        "$sum": {"$cond": [{"$ne": ["$workflow_id", None]}, 1, 0]}
                    },
                    "count": {"$sum": 1},
                    # 读取第一个模板的 system_prompt 内容（前 800 字作为摘要）
                    "system_prompt_preview": {"$first": "$content.system_prompt"},
                }},
            ]
            results = await self._db.prompt_templates.aggregate(pipeline).to_list(length=500)
            for r in results:
                preview = r.get("system_prompt_preview") or ""
                # 截取前 800 字作为预览，避免上下文过长
                if len(preview) > 800:
                    preview = preview[:800] + "...(截断)"
                summaries.append({
                    "agent_type": r["_id"]["agent_type"],
                    "agent_name": r["_id"]["agent_name"],
                    "template_count": r["count"],
                    "has_workflow_specific": r["has_workflow_specific"] > 0,
                    "template_names": r["template_names"][:3],  # 最多展示3个
                    "system_prompt_preview": preview,
                })
        except Exception as e:
            logger.warning(f"收集提示词模板摘要失败: {e}")
        return summaries

    def _get_node_types(self) -> List[Dict[str, str]]:
        """获取可用的节点类型说明"""
        return [
            {"type": "start", "description": "工作流起始节点，每个工作流必须有且仅有一个"},
            {"type": "end", "description": "工作流结束节点，每个工作流必须有且仅有一个"},
            {"type": "analyst", "description": "分析师节点，执行特定分析任务（技术分析、基本面、新闻等），需要关联 agent_id"},
            {"type": "researcher", "description": "研究员节点，综合分析报告进行研究（看多/看空），需要关联 agent_id"},
            {"type": "trader", "description": "研究整合员节点，生成用户版研究简报，需要关联 agent_id"},
            {"type": "risk", "description": "风险分析节点，评估风险（高弹性/防御/基准），需要关联 agent_id"},
            {"type": "manager", "description": "管理者节点，综合多方观点形成研究结论，需要关联 agent_id"},
            {"type": "parallel", "description": "并行开始节点，之后的多个分支并行执行"},
            {"type": "merge", "description": "并行合并节点，等待多个分支完成"},
            {"type": "debate", "description": "多情景研究节点，多个 Agent 进行多轮情景研究（如积极/谨慎情景研究、风险情景研究）"},
            {"type": "post_processor", "description": "后处理节点，对分析结果进行汇总或格式化"},
            {"type": "condition", "description": "条件节点，根据条件选择不同分支"},
        ]

    def _build_context_text(
        self,
        agents: List[Dict[str, Any]],
        prompt_summaries: List[Dict[str, str]],
        node_types: List[Dict[str, str]],
    ) -> str:
        """
        构建 LLM 可理解的上下文文本

        压缩策略:
        - Agent: 只传 id, name, description, category（不传完整 tools 列表）
        - 提示词: 只传摘要（哪些 agent 有自定义模板）
        - 按 category 分组
        - 不传工具/技能列表（由 CapabilityIndex 精准搜索替代）
        """
        sections = []

        # Agent 列表
        prompt_map = {s["agent_name"]: s for s in prompt_summaries}

        # 🔍 调试：打印传给 LLM 的 Agent 完整列表
        agent_ids = [a["id"] for a in agents]
        logger.info(
            f"📋 [ResourceCollector] 传给 LLM 的 Agent 列表 (共 {len(agents)} 个): "
            f"{agent_ids}"
        )

        sections.append("## 可用的 Agent（智能体）\n")
        categories: Dict[str, List] = {}
        for a in agents:
            cat = a.get("category", "other")
            categories.setdefault(cat, []).append(a)
        for cat, items in sorted(categories.items()):
            sections.append(f"### {cat}")
            for a in items:
                line = f"- **{a['id']}** ({a['name']}): {a['description']}"
                # 维护状态标记（非 MAINTAINED 时警告 LLM）
                status = a.get("maintenance_status", "maintained")
                if status and status != "maintained":
                    line += f"  ⚠️ [状态: {status}]"
                # 产出字段（帮助 LLM 理解数据流和 Agent 间协作）
                output_field = a.get("output_field", "")
                if output_field:
                    line += f"  [→ 产出字段: `{output_field}`]"
                # 附加提示词摘要和实际内容预览
                ps = prompt_map.get(a["id"])
                if ps:
                    line += f"  [默认提示词: 有{ps['template_count']}个模板]"
                    preview = ps.get("system_prompt_preview", "")
                    if preview:
                        line += f"\n  <提示词预览>\n{preview}\n  </提示词预览>"
                else:
                    line += "  [默认提示词: 通用]"
                sections.append(line)
            sections.append("")

        # 节点类型
        sections.append("## 可用的工作流节点类型\n")
        for nt in node_types:
            sections.append(f"- **{nt['type']}**: {nt['description']}")
        sections.append("")

        return "\n".join(sections)

