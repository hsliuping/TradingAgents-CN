
import os
import yaml
import logging
from typing import List, Dict, Any, Callable, Optional

from tradingagents.agents.utils.generic_agent import GenericAgent
from tradingagents.tools.registry import get_all_tools
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module

logger = get_logger("analysts.dynamic")

class DynamicAnalystFactory:
    """
    动态分析师工厂
    根据配置文件动态生成智能体，不再需要为每个角色编写单独的 Python 文件。
    """
    
    _config_cache = {}
    _config_mtime = {}

    @classmethod
    def load_config(cls, config_path: str = None) -> Dict[str, Any]:
        """加载智能体配置文件"""
        if not config_path:
            # 默认使用 tradingagents/agents/phase1_agents_config.yaml
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # tradingagents/agents/analysts -> tradingagents/agents
            agents_dir = os.path.dirname(current_dir)
            config_path = os.path.join(agents_dir, "phase1_agents_config.yaml")

        try:
            mtime = os.path.getmtime(config_path)
        except Exception:
            mtime = None

        # 命中缓存且文件未变化则复用
        if (
            config_path in cls._config_cache
            and config_path in cls._config_mtime
            and mtime is not None
            and cls._config_mtime.get(config_path) == mtime
        ):
            return cls._config_cache[config_path]

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                cls._config_cache[config_path] = config or {}
                if mtime is not None:
                    cls._config_mtime[config_path] = mtime
                return cls._config_cache[config_path]
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败: {config_path}, 错误: {e}")
            return {}

    @classmethod
    def get_agent_config(cls, slug_or_name: str, config_path: str = None) -> Optional[Dict[str, Any]]:
        """
        根据 slug 或中文名称获取特定智能体的配置
        
        Args:
            slug_or_name: 智能体标识符（slug）或中文名称（name）
            config_path: 配置文件路径 (可选)
            
        Returns:
            智能体配置字典，如果未找到则返回 None
        """
        config = cls.load_config(config_path)
        
        # 检查 customModes - 先按 slug 查找，再按 name 查找
        for agent in config.get('customModes', []):
            if agent.get('slug') == slug_or_name:
                return agent
            if agent.get('name') == slug_or_name:
                return agent
                
        # 检查 agents (如果配置结构不同)
        for agent in config.get('agents', []):
            if agent.get('slug') == slug_or_name:
                return agent
            if agent.get('name') == slug_or_name:
                return agent
                
        return None

    @classmethod
    def get_slug_by_name(cls, name: str, config_path: str = None) -> Optional[str]:
        """
        根据中文名称获取对应的 slug
        
        Args:
            name: 智能体中文名称
            config_path: 配置文件路径 (可选)
            
        Returns:
            对应的 slug，如果未找到则返回 None
        """
        config = cls.load_config(config_path)
        
        # 检查 customModes
        for agent in config.get('customModes', []):
            if agent.get('name') == name:
                return agent.get('slug')
                
        # 检查 agents
        for agent in config.get('agents', []):
            if agent.get('name') == name:
                return agent.get('slug')
                
        return None

    @classmethod
    def get_all_agents(cls, config_path: str = None) -> List[Dict[str, Any]]:
        """
        获取所有配置的智能体列表
        
        Args:
            config_path: 配置文件路径 (可选)
            
        Returns:
            智能体配置列表
        """
        config = cls.load_config(config_path)
        agents = []
        
        # 从 customModes 获取
        agents.extend(config.get('customModes', []))
        
        # 从 agents 获取（如果配置结构不同）
        agents.extend(config.get('agents', []))
        
        return agents

    @classmethod
    def build_lookup_map(cls, config_path: str = None) -> Dict[str, Dict[str, Any]]:
        """
        构建一个查找映射，支持通过多种方式查找智能体配置
        
        映射的 key 包括：
        - slug (如 "market-analyst")
        - 简短 ID (如 "market"，从 slug 派生)
        - 中文名称 (如 "市场技术分析师")
        
        Returns:
            Dict[str, Dict] - key 为各种标识符，value 为包含 internal_key, slug, tool_key 的字典
        """
        agents = cls.get_all_agents(config_path)
        lookup = {}
        
        for agent in agents:
            slug = agent.get('slug', '')
            name = agent.get('name', '')
            
            if not slug:
                continue
            
            # 生成 internal_key（去除 -analyst 后缀，替换 - 为 _）
            internal_key = slug.replace("-analyst", "").replace("-", "_")
            
            # 根据 slug 推断工具类型
            tool_key = cls._infer_tool_key(slug, name)
            
            # 构建配置信息
            config_info = {
                'internal_key': internal_key,
                'slug': slug,
                'tool_key': tool_key,
                'name': name,
                'display_name': internal_key.replace('_', ' ').title()
            }
            
            # 添加多种查找方式
            lookup[slug] = config_info  # 完整 slug
            lookup[internal_key] = config_info  # 简短 ID
            if name:
                lookup[name] = config_info  # 中文名称
        
        return lookup

    @classmethod
    def _infer_tool_key(cls, slug: str, name: str = "") -> str:
        """
        根据 slug 和名称推断应该使用的工具类型
        
        Args:
            slug: 智能体 slug
            name: 智能体中文名称
            
        Returns:
            工具类型 key (market, news, social, fundamentals)
        """
        search_key = slug.lower()
        name_lower = name.lower() if name else ""
        
        if "news" in search_key or "新闻" in name:
            return "news"
        elif "social" in search_key or "sentiment" in search_key or "社交" in name or "情绪" in name:
            return "social"
        elif "fundamental" in search_key or "基本面" in name:
            return "fundamentals"
        else:
            # 默认使用 market 工具
            return "market"

    @classmethod
    def _get_analyst_icon(cls, slug: str, name: str = "") -> str:
        """
        根据 slug 和名称推断分析师图标
        
        Args:
            slug: 智能体 slug
            name: 智能体中文名称
            
        Returns:
            图标 emoji
        """
        search_key = slug.lower()
        
        if "news" in search_key or "新闻" in name:
            return "📰"
        elif "social" in search_key or "sentiment" in search_key or "社交" in name or "情绪" in name:
            return "💬"
        elif "fundamental" in search_key or "基本面" in name:
            return "💼"
        elif "china" in search_key or "中国" in name:
            return "🇨🇳"
        elif "capital" in search_key or "资金" in name:
            return "💸"
        elif "market" in search_key or "市场" in name or "技术" in name:
            return "📊"
        else:
            return "🤖"

    @classmethod
    def build_node_mapping(cls, config_path: str = None) -> Dict[str, Optional[str]]:
        """
        动态构建节点名称映射表，用于进度更新
        
        映射 LangGraph 节点名称到中文显示名称
        
        Returns:
            Dict[str, Optional[str]] - key 为节点名称，value 为中文显示名称（None 表示跳过）
        """
        agents = cls.get_all_agents(config_path)
        node_mapping = {}
        
        for agent in agents:
            slug = agent.get('slug', '')
            name = agent.get('name', '')
            
            if not slug:
                continue
            
            # 生成 internal_key（去除 -analyst 后缀，替换 - 为 _）
            internal_key = slug.replace("-analyst", "").replace("-", "_")
            
            # 生成节点名称（首字母大写，如 "China_Market Analyst"）
            formatted_name = internal_key.replace('_', ' ').title().replace(' ', '_')
            analyst_node_name = f"{formatted_name} Analyst"
            
            # 获取图标
            icon = cls._get_analyst_icon(slug, name)
            
            # 添加分析师节点映射
            node_mapping[analyst_node_name] = f"{icon} {name}"
            
            # 添加工具节点映射（跳过）
            node_mapping[f"tools_{internal_key}"] = None
            
            # 添加消息清理节点映射（跳过）
            node_mapping[f"Msg Clear {formatted_name}"] = None
        
        # 添加固定的非分析师节点映射
        node_mapping.update({
            # 研究员节点
            'Bull Researcher': "🐂 看涨研究员",
            'Bear Researcher': "🐻 看跌研究员",
            'Research Manager': "👔 研究经理",
            # 交易员节点
            'Trader': "💼 交易员决策",
            # 风险评估节点
            'Risky Analyst': "🔥 激进风险评估",
            'Safe Analyst': "🛡️ 保守风险评估",
            'Neutral Analyst': "⚖️ 中性风险评估",
            'Risk Judge': "🎯 风险经理",
        })
        
        return node_mapping

    @classmethod
    def build_progress_map(cls, config_path: str = None) -> Dict[str, float]:
        """
        动态构建进度映射表，用于进度百分比计算
        
        Returns:
            Dict[str, float] - key 为中文显示名称，value 为进度百分比
        """
        agents = cls.get_all_agents(config_path)
        progress_map = {}
        
        # 分析师阶段占 10% - 50%，平均分配
        analyst_count = len(agents)
        if analyst_count > 0:
            analyst_progress_range = 40  # 10% 到 50%
            progress_per_analyst = analyst_progress_range / analyst_count
            
            for i, agent in enumerate(agents):
                slug = agent.get('slug', '')
                name = agent.get('name', '')
                
                if not slug or not name:
                    continue
                
                icon = cls._get_analyst_icon(slug, name)
                display_name = f"{icon} {name}"
                
                # 计算进度百分比（从 10% 开始）
                progress = 10 + (i + 1) * progress_per_analyst
                progress_map[display_name] = round(progress, 1)
        
        # 添加固定的非分析师节点进度
        progress_map.update({
            "🐂 看涨研究员": 51.25,
            "🐻 看跌研究员": 57.5,
            "👔 研究经理": 70,
            "💼 交易员决策": 78,
            "🔥 激进风险评估": 81.75,
            "🛡️ 保守风险评估": 85.5,
            "⚖️ 中性风险评估": 89.25,
            "🎯 风险经理": 93,
            "📊 生成报告": 97,
        })
        
        return progress_map

    @classmethod
    def clear_cache(cls):
        """清除配置缓存，用于配置文件更新后重新加载"""
        cls._config_cache.clear()
        cls._config_mtime.clear()
        logger.info("🔄 已清除智能体配置缓存")

    @classmethod
    def _mcp_settings_from_toolkit(cls, toolkit):
        """
        提取 MCP 相关开关和加载器，保持与统一工具注册逻辑兼容。
        """
        enable_mcp = False
        mcp_loader = None

        if isinstance(toolkit, dict):
            enable_mcp = bool(toolkit.get("enable_mcp", False))
            mcp_loader = toolkit.get("mcp_tool_loader")
        else:
            enable_mcp = bool(getattr(toolkit, "enable_mcp", False))
            mcp_loader = getattr(toolkit, "mcp_tool_loader", None)

        return enable_mcp, mcp_loader

    @classmethod
    def create_analyst(cls, slug: str, llm: Any, toolkit: Any, config_path: str = None) -> Callable:
        """
        创建动态分析师节点函数
        
        Args:
            slug: 智能体标识符 (如 "market-analyst")
            llm: LLM 实例
            toolkit: 工具集
            config_path: 配置文件路径 (可选)
            
        Returns:
            LangGraph 节点函数
        """
        agent_config = cls.get_agent_config(slug, config_path)
        if not agent_config:
            raise ValueError(f"未找到智能体配置: {slug}")
            
        name = agent_config.get("name", slug)
        role_definition = agent_config.get("roleDefinition", "")
        
        logger.info(f"🤖 创建动态智能体: {name} ({slug})")
        
        # 获取工具
        enable_mcp, mcp_loader = cls._mcp_settings_from_toolkit(toolkit)
        
        # 根据 slug 或配置筛选工具；默认全量
        tools = get_all_tools(
            toolkit=toolkit,
            enable_mcp=enable_mcp,
            mcp_tool_loader=mcp_loader
        )
        allowed_tool_names = agent_config.get("tools") or []
        if allowed_tool_names:
            allowed_set = {str(name).strip() for name in allowed_tool_names if str(name).strip()}
            filtered_tools = [
                tool for tool in tools
                if getattr(tool, "name", None) in allowed_set
            ]
            if filtered_tools:
                tools = filtered_tools
                logger.info(f"🔧 工具已按配置裁剪: {len(tools)}/{len(allowed_set)} 个匹配")
            else:
                logger.warning(
                    "⚠️ 工具裁剪后为空，回退到全量工具。"
                    "请确认配置的工具名称与注册名称一致。"
                )
        
        # 实例化通用智能体
        agent = GenericAgent(
            name=name,
            slug=slug,
            llm=llm,
            tools=tools,
            system_message_template=role_definition
        )

        # 创建闭包函数作为节点
        # 使用 log_analyst_module 装饰器，模块名使用 slug 的简化版（去除 -analyst 后缀）
        module_name = slug.replace("-analyst", "").replace("-", "_")
        
        @log_analyst_module(module_name)
        def dynamic_analyst_node(state):
            return agent.run(state)

        return dynamic_analyst_node

# 便捷工厂函数
def create_dynamic_analyst(slug: str, llm: Any, toolkit: Any) -> Callable:
    return DynamicAnalystFactory.create_analyst(slug, llm, toolkit)
