"""
智能体基类

所有智能体都应继承此基类
v2.0 新增：标准化工具调用循环处理
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain_core.tools import BaseTool

from .config import AgentMetadata, AgentConfig

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_MAX_TOOL_ITERATIONS = 3  # 最大工具调用迭代次数


class BaseAgent(ABC):
    """
    智能体基类

    提供统一的接口和通用功能:
    - LLM 调用
    - 工具管理（支持动态绑定）
    - 提示词渲染
    - 状态管理
    - 日志记录

    v2.0 新特性:
    - 支持从配置或数据库动态加载工具
    - 支持 LangChain 工具集成
    - 支持元数据自动加载
    """

    # 子类需要定义的元数据
    metadata: AgentMetadata = None

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[List[str]] = None
    ):
        """
        初始化 Agent

        Args:
            config: Agent 配置（旧版兼容）
            llm: LangChain LLM 实例（新版）
            tool_ids: 工具 ID 列表（新版，可选）
        """
        self.config = config or AgentConfig()
        self._llm_client = None
        self._llm = llm  # LangChain LLM（新版）
        self._tools: Dict[str, Callable] = {}  # 旧版工具字典
        self._langchain_tools: List[BaseTool] = []  # 新版 LangChain 工具列表
        self._prompt_template: Optional[str] = None

        # v2.0: 动态加载工具
        if tool_ids is not None:
            self._load_tools_v2(tool_ids)

        logger.debug(f"Agent '{self.agent_id}' 初始化完成")
    
    @classmethod
    def get_metadata(cls) -> AgentMetadata:
        """获取智能体元数据"""
        if cls.metadata is None:
            raise NotImplementedError(f"{cls.__name__} 必须定义 metadata")
        return cls.metadata

    def set_dependencies(self, llm: BaseChatModel, toolkit: Optional[Any] = None):
        """
        设置依赖项（LLM和工具）

        由WorkflowEngine调用，用于注入LLM和工具依赖

        Args:
            llm: 语言模型实例
            toolkit: 工具集（可选）
        """
        self._llm = llm
        if toolkit and hasattr(toolkit, 'tools'):
            # 如果提供了toolkit，可以选择性地添加工具
            # 但不覆盖已有的工具
            pass
        logger.info(f"✅ Agent {self.agent_id} 已设置LLM依赖")

    def initialize(self) -> None:
        """
        初始化智能体
        
        子类可以覆盖此方法进行额外初始化
        """
        self._setup_llm()
        self._setup_tools()
        self._setup_prompt()
    
    def _setup_llm(self) -> None:
        """设置 LLM 客户端"""
        from ..llm import UnifiedLLMClient
        
        self._llm_client = UnifiedLLMClient.from_provider(
            provider=self.config.llm_provider,
            model=self.config.llm_model,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )
    
    def _setup_tools(self) -> None:
        """
        设置工具

        子类应覆盖此方法注册可用工具
        """
        pass

    def _load_tools_v2(self, tool_ids: List[str]) -> None:
        """
        v2.0: 从工具 ID 列表加载 LangChain 工具

        Args:
            tool_ids: 工具 ID 列表
        """
        from core.tools.registry import ToolRegistry

        registry = ToolRegistry()
        self._langchain_tools = []

        logger.info(f"🔧 [Agent {self.agent_id}] 开始加载工具: {tool_ids}")

        for tool_id in tool_ids:
            tool = registry.get_langchain_tool(tool_id)
            if tool:
                self._langchain_tools.append(tool)
                logger.info(f"✅ [Agent {self.agent_id}] 成功加载工具: {tool_id}")
            else:
                logger.warning(f"⚠️ [Agent {self.agent_id}] 工具未找到: {tool_id}")

        logger.info(f"🔧 [Agent {self.agent_id}] 工具加载完成: {len(self._langchain_tools)}/{len(tool_ids)} 个工具")

    def load_tools_from_config(self) -> List[str]:
        """
        v2.0: 从配置加载工具列表

        优先级:
        1. 数据库配置（BindingManager）
        2. 元数据中的默认工具
        3. 空列表

        Returns:
            工具 ID 列表
        """
        try:
            # 优先从数据库配置加载
            from core.config.binding_manager import BindingManager
            tool_ids = BindingManager().get_tools_for_agent(self.agent_id)

            if tool_ids:
                logger.info(f"📦 从数据库加载 {len(tool_ids)} 个工具: {tool_ids}")
                return tool_ids

            # 降级：使用元数据中的默认工具
            metadata = self.get_metadata()
            if hasattr(metadata, 'default_tools') and metadata.default_tools:
                logger.info(f"📦 从元数据加载 {len(metadata.default_tools)} 个默认工具")
                return metadata.default_tools

            if hasattr(metadata, 'tools') and metadata.tools:
                logger.info(f"📦 从元数据加载 {len(metadata.tools)} 个工具")
                return metadata.tools

            logger.warning(f"⚠️ Agent '{self.agent_id}' 没有配置工具")
            return []

        except Exception as e:
            logger.error(f"❌ 加载工具配置失败: {e}")
            return []
    
    def _setup_prompt(self) -> None:
        """
        设置提示词模板
        
        子类应覆盖此方法设置提示词
        """
        pass
    
    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """注册工具"""
        tool_def = self._llm_client.register_tool(func, name, description)
        tool_name = tool_def["function"]["name"]
        self._tools[tool_name] = func
    
    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行智能体逻辑
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态字典
        """
        pass
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """使智能体可调用，用于 LangGraph 节点"""
        return self.execute(state)
    
    def render_prompt(
        self,
        template: Optional[str] = None,
        **variables
    ) -> str:
        """
        渲染提示词模板
        
        Args:
            template: 提示词模板 (如果为 None，使用默认模板)
            **variables: 模板变量
            
        Returns:
            渲染后的提示词
        """
        tpl = template or self._prompt_template
        if tpl is None:
            return ""
        
        # 合并配置中的变量
        all_vars = {**self.config.prompt_variables, **variables}
        
        try:
            return tpl.format(**all_vars)
        except KeyError as e:
            # 记录警告但不中断
            return tpl
    
    def log(self, message: str, level: str = "info") -> None:
        """记录日志"""
        # TODO: 集成统一日志系统
        prefix = f"[{self.get_metadata().name}]"
        print(f"{prefix} {message}")
    
    @property
    def agent_id(self) -> str:
        """智能体 ID"""
        return self.get_metadata().id
    
    @property
    def agent_name(self) -> str:
        """智能体名称"""
        return self.get_metadata().name
    
    @property
    def llm(self):
        """LLM 客户端（旧版）或 LangChain LLM（新版）"""
        return self._llm or self._llm_client

    @property
    def tools(self) -> List[BaseTool]:
        """v2.0: 获取 LangChain 工具列表"""
        return self._langchain_tools

    @property
    def tool_names(self) -> List[str]:
        """v2.0: 获取工具名称列表"""
        return [tool.name for tool in self._langchain_tools]

    # ========== v2.0: 标准化工具调用循环处理 ==========

    def invoke_with_tools(
        self,
        messages: List,
        analysis_prompt: Optional[str] = None,
        max_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    ) -> str:
        """
        v2.0: 标准化的工具调用循环处理（自包含模式）

        这是推荐的 LLM + 工具调用方式，所有 Agent 都应该使用这个方法。

        流程:
        1. 调用 LLM（绑定工具）
        2. 如果 LLM 返回 tool_calls:
           a. 在 Agent 内部执行所有工具
           b. 将工具结果添加到消息历史
           c. 再次调用 LLM（不绑定工具）生成最终报告
        3. 返回最终报告内容

        Args:
            messages: 消息列表（包含 SystemMessage 和 HumanMessage）
            analysis_prompt: 工具执行后的分析提示词（可选）
            max_iterations: 最大工具调用迭代次数（防止死循环）

        Returns:
            str: 最终的分析报告内容
        """
        if not self._llm:
            raise ValueError("LLM 未配置，无法执行工具调用")

        current_messages = list(messages)

        logger.info(f"🚀 [{self.agent_id}] 开始工具调用循环，最大迭代次数: {max_iterations}")
        logger.info(f"🔧 [{self.agent_id}] 可用工具数量: {len(self._langchain_tools) if self._langchain_tools else 0}")
        if self._langchain_tools:
            logger.info(f"🔧 [{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")

        for iteration in range(max_iterations):
            logger.info(f"🔄 [{self.agent_id}] 工具调用迭代 {iteration + 1}/{max_iterations}")

            # 绑定工具并调用 LLM
            if self._langchain_tools:
                llm_with_tools = self._llm.bind_tools(self._langchain_tools)
                logger.info(f"🔗 [{self.agent_id}] LLM已绑定 {len(self._langchain_tools)} 个工具")
            else:
                llm_with_tools = self._llm
                logger.info(f"🔗 [{self.agent_id}] LLM未绑定工具")

            logger.info(f"💬 [{self.agent_id}] 调用LLM，消息数量: {len(current_messages)}")
            response = llm_with_tools.invoke(current_messages)
            logger.info(f"💬 [{self.agent_id}] LLM响应完成")

            # 检查是否有工具调用
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"🔧 [{self.agent_id}] 检测到 {len(response.tool_calls)} 个工具调用")

                # 执行所有工具调用
                tool_messages = self._execute_tool_calls(response.tool_calls)

                # 构建新的消息历史
                current_messages = current_messages + [response] + tool_messages

                # 添加分析提示词（如果提供）
                if analysis_prompt:
                    current_messages.append(HumanMessage(content=analysis_prompt))

                # 再次调用 LLM（不绑定工具，强制生成报告）
                logger.info(f"📝 [{self.agent_id}] 工具执行完成，生成最终报告...")
                final_response = self._llm.invoke(current_messages)

                content = final_response.content if hasattr(final_response, 'content') else str(final_response)
                logger.info(f"✅ [{self.agent_id}] 报告生成完成，长度: {len(content)} 字符")
                return content
            else:
                # 没有工具调用，直接返回内容
                content = response.content if hasattr(response, 'content') else str(response)
                logger.info(f"📝 [{self.agent_id}] 直接响应（无工具调用），长度: {len(content)} 字符")
                return content

        # 达到最大迭代次数
        logger.warning(f"⚠️ [{self.agent_id}] 达到最大迭代次数 {max_iterations}")
        return f"分析未能完成（达到最大迭代次数 {max_iterations}）"

    def _execute_tool_calls(self, tool_calls: List[Dict]) -> List[ToolMessage]:
        """
        执行工具调用并返回 ToolMessage 列表

        Args:
            tool_calls: 工具调用列表

        Returns:
            List[ToolMessage]: 工具执行结果消息列表
        """
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call.get('name')
            tool_args = tool_call.get('args', {})
            tool_id = tool_call.get('id')

            logger.info(f"🔧 [{self.agent_id}] 执行工具: {tool_name}")
            logger.info(f"🔧 [{self.agent_id}] 工具参数: {tool_args}")

            # 找到对应的工具并执行
            tool_result = None
            for tool in self._langchain_tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    try:
                        logger.info(f"🔄 [{self.agent_id}] 开始调用工具 {tool_name}...")
                        tool_result = tool.invoke(tool_args)

                        # 记录工具返回结果的详细信息
                        if isinstance(tool_result, str):
                            result_preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                            logger.info(f"✅ [{self.agent_id}] 工具 {tool_name} 执行成功，返回长度: {len(tool_result)} 字符")
                            logger.info(f"📄 [{self.agent_id}] 工具 {tool_name} 返回预览: {result_preview}")
                        else:
                            logger.info(f"✅ [{self.agent_id}] 工具 {tool_name} 执行成功，返回类型: {type(tool_result).__name__}")
                            logger.info(f"📄 [{self.agent_id}] 工具 {tool_name} 返回内容: {str(tool_result)[:200]}...")

                    except Exception as e:
                        logger.error(f"❌ [{self.agent_id}] 工具 {tool_name} 执行失败: {e}")
                        import traceback
                        logger.error(f"❌ [{self.agent_id}] 工具 {tool_name} 错误详情: {traceback.format_exc()}")
                        tool_result = f"工具执行失败: {str(e)}"
                    break

            if tool_result is None:
                tool_result = f"未找到工具: {tool_name}"
                logger.warning(f"⚠️ [{self.agent_id}] {tool_result}")
                logger.warning(f"⚠️ [{self.agent_id}] 可用工具列表: {[t.name for t in self._langchain_tools]}")

            # 创建工具消息
            tool_messages.append(ToolMessage(
                content=str(tool_result),
                tool_call_id=tool_id
            ))

        return tool_messages

