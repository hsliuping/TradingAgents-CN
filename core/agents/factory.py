"""
智能体工厂

负责创建和配置智能体实例

v2.0 新特性:
- 支持从配置或数据库动态加载工具
- 支持 LangChain LLM 集成
"""

import logging
from typing import Any, Dict, Optional, Type, List

from langchain_core.language_models import BaseChatModel

from .base import BaseAgent
from .config import AgentConfig, AgentMetadata, AgentMaintenanceStatus
from .registry import AgentRegistry, get_registry
from .universal import UniversalAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    智能体工厂
    
    用法:
        factory = AgentFactory()
        
        # 创建智能体实例
        agent = factory.create("market_analyst", config=my_config)
        
        # 批量创建
        agents = factory.create_many(["market_analyst", "news_analyst"])
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or get_registry()
    
    def create(
        self,
        agent_id: str,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[List[str]] = None,
        memory: Optional[Any] = None,
        **config_overrides
    ) -> BaseAgent:
        """
        创建智能体实例

        Args:
            agent_id: 智能体 ID
            config: 智能体配置（旧版）
            llm: LangChain LLM 实例（新版）
            tool_ids: 工具 ID 列表（新版，可选）
            memory: 记忆系统实例（v2.0，可选）
            **config_overrides: 配置覆盖参数

        Returns:
            初始化后的智能体实例
        """
        logger.info(f"[AgentFactory] 🏭 开始创建 Agent: {agent_id}")
        logger.info(f"   - config: {config.model_dump() if config else 'None'}")
        logger.info(f"   - llm: {type(llm).__name__ if llm else 'None'}")
        logger.info(f"   - tool_ids: {tool_ids}")
        logger.info(f"   - config_overrides: {config_overrides}")

        # 🔥 检查是否为废弃 Agent
        metadata = self.registry.get_metadata(agent_id)
        if metadata and metadata.maintenance_status == AgentMaintenanceStatus.DEPRECATED:
            import warnings
            warnings.warn(
                f"Agent '{agent_id}' 已废弃，请使用 v2 版本（如 '{agent_id}_v2'）。"
                f"该 Agent 将在未来的版本中被移除。",
                DeprecationWarning,
                stacklevel=3
            )
            logger.warning(f"[AgentFactory] ⚠️ Agent '{agent_id}' 已废弃，建议使用 v2 版本")

        agent_class = self.registry.get(agent_id)

        if agent_class is None:
            # 🆕 降级：尝试从 agent_configs 数据库加载并创建 UniversalAgent
            universal = self._try_create_universal_agent(
                agent_id, config, llm, tool_ids, memory
            )
            if universal is not None:
                return universal
            raise ValueError(f"智能体 '{agent_id}' 未注册实现，且在 agent_configs 中也找不到对应配置")

        # 合并配置
        if config is None:
            config = AgentConfig()

        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # v2.0: 检查 Agent 支持的参数
        import inspect
        supports_llm = False
        supports_memory = False

        if llm is not None or memory is not None:
            try:
                sig = inspect.signature(agent_class.__init__)
                supports_llm = "llm" in sig.parameters
                supports_memory = "memory" in sig.parameters
                logger.info(f"[AgentFactory] 🔍 检查 Agent 构造函数签名:")
                logger.info(f"   - Agent 类: {agent_class.__name__}")
                logger.info(f"   - 支持 llm 参数: {supports_llm}")
                logger.info(f"   - 支持 memory 参数: {supports_memory}")
                logger.info(f"   - 构造函数参数: {list(sig.parameters.keys())}")
            except Exception as e:
                logger.warning(f"[AgentFactory] ⚠️ 检查构造函数签名失败: {e}")

        try:
            # 构建初始化参数
            init_kwargs = {"config": config}

            if llm is not None and supports_llm:
                init_kwargs["llm"] = llm
                logger.info(f"[AgentFactory] ✅ 将传入 LLM 参数: {type(llm).__name__}")
            elif llm is not None and not supports_llm:
                logger.warning(
                    f"[AgentFactory] ⚠️ Agent {agent_id} 的构造函数不支持 llm 参数，"
                    f"但调用方传入了 llm。将使用旧版依赖注入方式。"
                )
            elif llm is None:
                logger.warning(
                    f"[AgentFactory] ⚠️ 调用方未传入 llm 参数。"
                    f"Agent {agent_id} 将需要从配置或环境变量创建 LLM 客户端。"
                )

            if tool_ids is not None and supports_llm:
                init_kwargs["tool_ids"] = tool_ids

            if memory is not None and supports_memory:
                init_kwargs["memory"] = memory

            # 创建 Agent
            if len(init_kwargs) > 1:  # 有额外参数
                logger.info(f"[AgentFactory] ✅ 使用 v2.0 方式创建 Agent: {agent_id}")
                logger.info(f"   - 传递参数: {list(init_kwargs.keys())}")
                agent = agent_class(**init_kwargs)
            else:
                logger.info(f"[AgentFactory] ⚠️ 使用旧版方式创建 Agent: {agent_id}")
                agent = agent_class(config)

        except TypeError as e:
            error_msg = str(e)
            if "unexpected keyword argument" in error_msg:
                logger.warning(f"[AgentFactory] ⚠️ Agent {agent_id} 不支持部分 v2.0 参数，降级为旧版方式")
                logger.warning(f"   - 错误: {e}")
                agent = agent_class(config)
            else:
                logger.error(f"[AgentFactory] ❌ 创建 Agent 失败: {e}")
                raise

        # 旧版适配：如果提供了 llm，但构造函数不支持，尝试注入依赖
        if llm is not None and not supports_llm and hasattr(agent, "set_dependencies"):
            try:
                from tradingagents.agents.utils.agent_utils import Toolkit
                try:
                    from tradingagents.default_config import DEFAULT_CONFIG
                    toolkit = Toolkit(config=DEFAULT_CONFIG)
                except Exception:
                    toolkit = Toolkit()
                agent.set_dependencies(llm, toolkit)
                logger.info(f"已为 Agent {agent_id} 注入旧版依赖 (LLM/Toolkit)")
            except Exception as dep_err:
                logger.warning(f"为 Agent {agent_id} 注入依赖失败: {dep_err}")

        # 初始化（如果需要）
        if hasattr(agent, 'initialize'):
            logger.info(f"[AgentFactory] 🔧 调用 Agent.initialize()")
            agent.initialize()

        # 🔍 打印 Agent 的最终状态
        logger.info(f"[AgentFactory] ✅ Agent 创建完成: {agent_id}")
        logger.info(f"   - Agent 类型: {type(agent).__name__}")
        logger.info(f"   - 是否有 _llm: {hasattr(agent, '_llm')}")
        logger.info(f"   - 是否有 _tools: {hasattr(agent, '_tools')}")
        if hasattr(agent, '_llm'):
            logger.info(f"   - _llm 值: {type(agent._llm).__name__ if agent._llm else 'None'}")
        if hasattr(agent, '_tools'):
            logger.info(f"   - _tools 值: {agent._tools}")
            if agent._tools:
                logger.info(f"   - 工具数量: {len(agent._tools)}")
                logger.info(f"   - 工具名称: {[t.name if hasattr(t, 'name') else str(t) for t in agent._tools]}")

        return agent

    def _try_create_universal_agent(
        self,
        agent_id: str,
        config: Optional[AgentConfig],
        llm: Optional[Any],
        tool_ids: Optional[List[str]],
        memory: Optional[Any],
    ) -> Optional[BaseAgent]:
        """
        尝试从 agent_configs 数据库加载配置，创建 UniversalAgent。

        当 agent_id 不在硬编码注册表中时调用，实现"数据库驱动的新 Agent"能力。

        Args:
            agent_id: 要创建的 Agent ID
            config: 运行时配置（可能为 None）
            llm: LangChain LLM 实例
            tool_ids: 工具列表（可能已由 WorkflowBuilder 解析好）
            memory: 记忆系统实例

        Returns:
            UniversalAgent 实例，或 None（若数据库中也找不到）
        """
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            if db is None:
                logger.warning(f"[AgentFactory] 数据库未连接，无法创建 UniversalAgent: {agent_id}")
                return None

            doc = db.agent_configs.find_one({
                "agent_id": agent_id,
                "enabled": True,
                "$or": [
                    {"metadata.source": {"$ne": "agent_workshop"}},
                    {"metadata.source": "agent_workshop", "version_status": {"$in": ["active", "testing"]}, "runtime_status": "active"},
                ],
            })
            if doc is None:
                logger.debug(f"[AgentFactory] agent_configs 中找不到可运行的 '{agent_id}'，无法创建 UniversalAgent")
                return None

            agent_name = doc.get("name") or doc.get("agent_name") or agent_id
            agent_description = doc.get("description") or f"{agent_name} - 由数据库配置驱动"
            output_field = doc.get("output_field") or "analysis_report"

            # 工具列表：优先使用调用方传入的（WorkflowBuilder 已解析的），
            # 否则读取 agent_configs 的 default_tools
            resolved_tool_ids = tool_ids
            if not resolved_tool_ids:
                resolved_tool_ids = doc.get("default_tools") or doc.get("tools") or []

            if config is None:
                config = AgentConfig()

            logger.info(
                f"[AgentFactory] 🌐 从 agent_configs 创建 UniversalAgent: {agent_id} "
                f"(name={agent_name}, output_field={output_field}, tools={resolved_tool_ids})"
            )

            agent = UniversalAgent(
                config=config,
                llm=llm,
                tool_ids=resolved_tool_ids,
                agent_id=agent_id,
                agent_name=agent_name,
                agent_description=agent_description,
                output_field=output_field,
                prompt_template_type=str(doc.get("prompt_template_type") or "universal"),
                prompt_template_name=str(doc.get("prompt_template_name") or agent_id),
                prompt_template_id=str(((doc.get("metadata") or {}).get("template_id") or "")).strip() or None,
                prompt_template_status=str(((doc.get("metadata") or {}).get("template_status") or "")).strip() or None,
                version_status=str(((doc.get("metadata") or {}).get("version_status") or "")).strip() or None,
            )

            if memory is not None and hasattr(agent, "_memory"):
                agent._memory = memory

            if hasattr(agent, "initialize"):
                agent.initialize()

            logger.info(f"[AgentFactory] ✅ UniversalAgent 创建成功: {agent_id}")
            return agent

        except Exception as e:
            logger.warning(f"[AgentFactory] ⚠️ 创建 UniversalAgent 失败 ({agent_id}): {e}")
            return None

    def create_with_dynamic_tools(
        self,
        agent_id: str,
        llm: BaseChatModel,
        config: Optional[AgentConfig] = None
    ) -> BaseAgent:
        """
        v2.0: 创建智能体实例，自动从配置加载工具

        Args:
            agent_id: 智能体 ID
            llm: LangChain LLM 实例
            config: 智能体配置（可选）

        Returns:
            初始化后的智能体实例
        """
        # 从配置加载工具列表
        from core.config.binding_manager import BindingManager
        tool_ids = BindingManager().get_tools_for_agent(agent_id)

        if not tool_ids:
            # 降级：使用元数据中的默认工具
            metadata = self.registry.get_metadata(agent_id)
            if metadata:
                tool_ids = getattr(metadata, 'default_tools', None) or getattr(metadata, 'tools', [])

        logger.info(f"为 Agent '{agent_id}' 加载工具: {tool_ids}")

        return self.create(
            agent_id=agent_id,
            config=config,
            llm=llm,
            tool_ids=tool_ids
        )
    
    def create_many(
        self,
        agent_ids: list,
        shared_config: Optional[AgentConfig] = None,
        **config_overrides
    ) -> Dict[str, BaseAgent]:
        """
        批量创建智能体
        
        Args:
            agent_ids: 智能体 ID 列表
            shared_config: 共享配置
            **config_overrides: 配置覆盖
            
        Returns:
            {agent_id: agent_instance} 字典
        """
        agents = {}
        for agent_id in agent_ids:
            try:
                agents[agent_id] = self.create(
                    agent_id, 
                    config=shared_config, 
                    **config_overrides
                )
            except ValueError as e:
                # 记录警告但继续创建其他智能体
                print(f"警告: {e}")
        
        return agents
    
    def get_available_agents(self) -> list:
        """获取所有已注册实现的智能体 ID"""
        return [
            m.id for m in self.registry.list_all()
            if self.registry.is_registered(m.id)
        ]
    
    def get_agent_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """获取智能体元数据"""
        return self.registry.get_metadata(agent_id)


# 便捷函数
def create_agent(
    agent_id: str,
    config: Optional[AgentConfig] = None,
    llm: Optional[BaseChatModel] = None,
    tool_ids: Optional[List[str]] = None,
    memory: Optional[Any] = None,
    **kwargs
) -> BaseAgent:
    """
    便捷函数: 创建智能体

    用法:
        from core.agents import create_agent

        # 旧版
        agent = create_agent("market_analyst", llm_provider="deepseek")

        # 新版（v2.0）
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("market_analyst", llm=llm, tool_ids=["get_stock_market_data_unified"])

        # v2.0 with memory
        from core.memory import MemoryManager
        memory_mgr = MemoryManager(embedding_mgr)
        agent_memory = memory_mgr.get_agent_memory("market_analyst")
        agent = create_agent("market_analyst", llm=llm, memory=agent_memory)
    """
    factory = AgentFactory()
    return factory.create(agent_id, config, llm=llm, tool_ids=tool_ids, memory=memory, **kwargs)


def create_agent_with_dynamic_tools(
    agent_id: str,
    llm: BaseChatModel,
    config: Optional[AgentConfig] = None
) -> BaseAgent:
    """
    v2.0 便捷函数: 创建智能体，自动从配置加载工具

    用法:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("market_analyst", llm)
    """
    factory = AgentFactory()
    return factory.create_with_dynamic_tools(agent_id, llm, config)
