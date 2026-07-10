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

    async def collect_all(self) -> Dict[str, Any]:
        """
        收集所有可用资源

        Returns:
            {
                "agents": [...],
                "tools": [...],
                "external_skills": [...],
                "prompt_summaries": [...],
                "node_types": [...],
                "context_text": "..."   # 汇总的文本描述，直接嵌入 LLM System Prompt
            }
        """
        agents = await self._collect_agents()
        tools = self._collect_tools()
        skills = await self._collect_external_skills()
        prompt_summaries = await self._collect_prompt_summaries()
        node_types = self._get_node_types()

        context_text = self._build_context_text(
            agents, tools, skills, prompt_summaries, node_types
        )

        return {
            "agents": agents,
            "tools": tools,
            "external_skills": skills,
            "prompt_summaries": prompt_summaries,
            "node_types": node_types,
            "context_text": context_text,
        }

    async def _collect_agents(self) -> List[Dict[str, Any]]:
        """收集可用的 Agent 列表"""
        agents = []

        # 1. 从内置配置收集
        try:
            from core.agents.config import BUILTIN_AGENTS
            for agent_id, meta in BUILTIN_AGENTS.items():
                agents.append({
                    "id": meta.id,
                    "name": meta.name,
                    "description": meta.description,
                    "category": meta.category.value if hasattr(meta.category, 'value') else str(meta.category),
                    "default_tools": list(meta.default_tools),
                    "source": "builtin",
                })
        except Exception as e:
            logger.warning(f"加载内置 Agent 失败: {e}")

        # 2. 从 MongoDB 补充（用户可能创建了自定义 Agent）
        if self._db is not None:
            try:
                db_agents = self._db.agent_configs.find({"enabled": True})
                builtin_ids = {a["id"] for a in agents}
                async for doc in db_agents:
                    aid = doc.get("agent_id", "")
                    if aid and aid not in builtin_ids:
                        agents.append({
                            "id": aid,
                            "name": doc.get("name", aid),
                            "description": doc.get("description", ""),
                            "category": doc.get("category", "custom"),
                            "default_tools": doc.get("default_tools", []),
                            "source": "database",
                        })
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

        只获取每个 Agent 是否有自定义模板（不传完整内容），
        帮助 AI 评估是否需要生成新的提示词。
        """
        summaries = []
        if self._db is None:
            return summaries
        try:
            # 获取系统默认提示词的摘要
            pipeline = [
                {"$match": {"status": "active", "is_system": True}},
                {"$group": {
                    "_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"},
                    "template_names": {"$push": "$template_name"},
                    "has_workflow_specific": {
                        "$sum": {"$cond": [{"$ne": ["$workflow_id", None]}, 1, 0]}
                    },
                    "count": {"$sum": 1},
                }},
            ]
            results = await self._db.prompt_templates.aggregate(pipeline).to_list(length=500)
            for r in results:
                summaries.append({
                    "agent_type": r["_id"]["agent_type"],
                    "agent_name": r["_id"]["agent_name"],
                    "template_count": r["count"],
                    "has_workflow_specific": r["has_workflow_specific"] > 0,
                    "template_names": r["template_names"][:3],  # 最多展示3个
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
            {"type": "trader", "description": "交易员节点，制定交易策略，需要关联 agent_id"},
            {"type": "risk", "description": "风险分析节点，评估风险（激进/保守/中性），需要关联 agent_id"},
            {"type": "manager", "description": "管理者节点，综合多方观点做出决策，需要关联 agent_id"},
            {"type": "parallel", "description": "并行开始节点，之后的多个分支并行执行"},
            {"type": "merge", "description": "并行合并节点，等待所有并行分支完成"},
            {"type": "debate", "description": "辩论节点，多个 Agent 进行多轮辩论（如多空辩论、风险辩论）"},
            {"type": "post_processor", "description": "后处理节点，对分析结果进行汇总或格式化"},
            {"type": "condition", "description": "条件节点，根据条件选择不同分支"},
        ]

    def _build_context_text(
        self,
        agents: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        skills: List[Dict[str, Any]],
        prompt_summaries: List[Dict[str, str]],
        node_types: List[Dict[str, str]],
    ) -> str:
        """
        构建 LLM 可理解的上下文文本

        压缩策略:
        - Agent: 只传 id, name, description, category（不传完整 tools 列表）
        - 工具: 只传 id, name, description
        - 提示词: 只传摘要（哪些 agent 有自定义模板）
        - 按 category 分组
        """
        sections = []

        # Agent 列表
        prompt_map = {s["agent_name"]: s for s in prompt_summaries}
        sections.append("## 可用的 Agent（智能体）\n")
        categories: Dict[str, List] = {}
        for a in agents:
            cat = a.get("category", "other")
            categories.setdefault(cat, []).append(a)
        for cat, items in sorted(categories.items()):
            sections.append(f"### {cat}")
            for a in items:
                line = f"- **{a['id']}** ({a['name']}): {a['description']}"
                # 附加提示词摘要
                ps = prompt_map.get(a["id"])
                if ps:
                    line += f"  [默认提示词: 有{ps['template_count']}个模板]"
                else:
                    line += "  [默认提示词: 通用]"
                sections.append(line)
            sections.append("")

        # 工具列表（压缩：只展示 id 和名称描述，按 category 分组）
        sections.append("## 可用的工具\n")
        tool_cats: Dict[str, List] = {}
        for t in tools:
            cat = t.get("category", "other")
            tool_cats.setdefault(cat, []).append(t)
        for cat, items in sorted(tool_cats.items()):
            sections.append(f"### {cat}")
            for t in items:
                sections.append(f"- **{t['id']}** ({t['name']}): {t['description']}")
            sections.append("")

        # 外部 Skill
        if skills:
            sections.append("## 用户创建的 Skill\n")
            for s in skills:
                sections.append(f"- **{s['id']}** ({s['name']}): {s['description']}")
            sections.append("")

        # 节点类型
        sections.append("## 可用的工作流节点类型\n")
        for nt in node_types:
            sections.append(f"- **{nt['type']}**: {nt['description']}")
        sections.append("")

        return "\n".join(sections)

