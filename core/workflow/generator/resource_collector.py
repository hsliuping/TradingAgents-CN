"""
资源收集器 — 从系统中收集可用资源供 AI 规划使用

收集内容：
1. BUILTIN_AGENTS — 内置 Agent 列表（id, name, description, category, tools）
2. BUILTIN_TOOLS — 内置工具列表（id, name, description, category）
3. external_skills — MongoDB 中的外部 Skill
4. agent_configs — MongoDB 中的 Agent 配置（可能包含用户自定义 Agent）
5. prompt_templates — 提示词模板（用于理解 Agent 能力）
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceCollector:
    """
    资源收集器

    从代码配置和 MongoDB 收集所有可用资源，
    构建 LLM 可理解的上下文文本。
    """

    def __init__(self, db=None):
        """
        Args:
            db: MongoDB 数据库实例（可选，不传则只使用内置配置）
        """
        self._db = db

    def set_database(self, db) -> None:
        self._db = db

    def collect_all(self) -> Dict[str, Any]:
        """
        收集所有可用资源

        Returns:
            {
                "agents": [...],
                "tools": [...],
                "external_skills": [...],
                "node_types": [...],
                "context_text": "..."   # 汇总的文本描述
            }
        """
        agents = self._collect_agents()
        tools = self._collect_tools()
        skills = self._collect_external_skills()
        node_types = self._get_node_types()

        context_text = self._build_context_text(agents, tools, skills, node_types)

        return {
            "agents": agents,
            "tools": tools,
            "external_skills": skills,
            "node_types": node_types,
            "context_text": context_text,
        }

    def _collect_agents(self) -> List[Dict[str, Any]]:
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
                for doc in db_agents:
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

    def _collect_external_skills(self) -> List[Dict[str, Any]]:
        """收集外部 Skill"""
        skills = []
        if self._db is None:
            return skills
        try:
            docs = self._db.external_skills.find({"status": "active"})
            for doc in docs:
                skills.append({
                    "id": doc.get("tool_id", ""),
                    "name": doc.get("display_name", ""),
                    "description": doc.get("description", ""),
                    "category": doc.get("metadata", {}).get("category", "external"),
                    "source": "external_skill",
                })
        except Exception as e:
            logger.warning(f"从数据库加载外部 Skill 失败: {e}")
        return skills

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
        ]

    def _build_context_text(
        self,
        agents: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        skills: List[Dict[str, Any]],
        node_types: List[Dict[str, str]],
    ) -> str:
        """构建 LLM 可理解的上下文文本"""
        sections = []

        # Agent 列表
        sections.append("## 可用的 Agent（智能体）\n")
        # 按 category 分组
        categories: Dict[str, List] = {}
        for a in agents:
            cat = a.get("category", "other")
            categories.setdefault(cat, []).append(a)
        for cat, items in sorted(categories.items()):
            sections.append(f"### {cat}")
            for a in items:
                tools_str = ", ".join(a.get("default_tools", [])[:5])
                sections.append(
                    f"- **{a['id']}** ({a['name']}): {a['description']}"
                    + (f"  [默认工具: {tools_str}]" if tools_str else "")
                )
            sections.append("")

        # 工具列表
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
            sections.append("## 外部 Skill（AI 生成的工具）\n")
            for s in skills:
                sections.append(f"- **{s['id']}** ({s['name']}): {s['description']}")
            sections.append("")

        # 节点类型
        sections.append("## 可用的工作流节点类型\n")
        for nt in node_types:
            sections.append(f"- **{nt['type']}**: {nt['description']}")
        sections.append("")

        return "\n".join(sections)

