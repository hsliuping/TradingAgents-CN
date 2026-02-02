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
        logger.info(f"[BaseAgent] 🚀 开始初始化 Agent")
        # 🔥 排除 llm_provider 和 llm_model，因为这些不应该在 Agent 配置中
        config_dict_log = config.model_dump(exclude={'llm_provider', 'llm_model'}) if config else None
        logger.info(f"   - config: {config_dict_log}")
        logger.info(f"   - llm: {type(llm).__name__ if llm else 'None'}")
        logger.info(f"   - tool_ids: {tool_ids}")

        self.config = config or AgentConfig()
        self._llm_client = None
        self._llm = llm  # LangChain LLM（新版）
        self._tools: Dict[str, Callable] = {}  # 旧版工具字典
        self._langchain_tools: List[BaseTool] = []  # 新版 LangChain 工具列表
        self._prompt_template: Optional[str] = None

        # v2.0: 动态加载工具
        if tool_ids is not None:
            logger.info(f"[BaseAgent] 🔧 开始加载工具: {tool_ids}")
            self._load_tools_v2(tool_ids)
            logger.info(f"[BaseAgent] ✅ 工具加载完成，工具数量: {len(self._langchain_tools)}")
        else:
            logger.info(f"[BaseAgent] ⚠️ 未提供 tool_ids，跳过工具加载")

        logger.info(f"[BaseAgent] ✅ Agent 初始化完成")
        logger.info(f"   - Agent ID: {self.agent_id if hasattr(self, 'agent_id') else 'N/A'}")
        logger.info(f"   - _llm: {type(self._llm).__name__ if self._llm else 'None'}")
        logger.info(f"   - _langchain_tools 数量: {len(self._langchain_tools)}")
    
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
        logger.info(f"[BaseAgent.initialize] 🔧 开始初始化 Agent: {self.agent_id}")
        logger.info(f"   - _llm 值: {type(self._llm).__name__ if self._llm else 'None'}")
        logger.info(f"   - _llm_client 值: {type(self._llm_client).__name__ if self._llm_client else 'None'}")
        
        # 🔥 如果已经传入了 llm，就不需要创建 _llm_client
        # LLM provider 和 model 应该由分析流程指定，而不是 Agent 配置
        if self._llm is None:
            logger.warning(
                f"⚠️ Agent {self.agent_id} 的 _llm 为 None，将尝试从配置创建 LLM 客户端。"
                f"这通常不应该发生，因为 LLM 应该由 WorkflowBuilder 在创建 Agent 时传入。"
                f"请检查：1) WorkflowBuilder 是否正确传入了 llm 参数；2) AgentFactory 是否正确传递了 llm 参数。"
            )
            self._setup_llm()
        else:
            logger.info(f"✅ Agent {self.agent_id} 已传入 LLM 实例: {type(self._llm).__name__}")
            # 🔍 验证 LLM 实例是否有 API key
            if hasattr(self._llm, 'openai_api_key'):
                api_key_val = self._llm.openai_api_key
                if hasattr(api_key_val, 'get_secret_value'):
                    api_key_val = api_key_val.get_secret_value()
                logger.info(f"   - LLM API Key: {'有值' if api_key_val else '空'}")
            elif hasattr(self._llm, 'api_key'):
                api_key_val = self._llm.api_key
                if hasattr(api_key_val, 'get_secret_value'):
                    api_key_val = api_key_val.get_secret_value()
                logger.info(f"   - LLM API Key: {'有值' if api_key_val else '空'}")
        
        logger.info(f"[BaseAgent.initialize] 🔧 开始设置工具...")
        self._setup_tools()
        logger.info(f"[BaseAgent.initialize] 🔧 开始设置提示词...")
        self._setup_prompt()
        logger.info(f"[BaseAgent.initialize] ✅ Agent {self.agent_id} 初始化完成")
    
    def _setup_llm(self) -> None:
        """
        设置 LLM 客户端（仅在未传入 llm 时调用）
        
        ⚠️ 注意：此方法会从环境变量读取 API key，这通常不应该发生。
        正确的做法是在创建 Agent 时传入已配置好的 LLM 实例。
        """
        from ..llm import UnifiedLLMClient
        
        # 🔥 如果 config 中没有 llm_provider 和 llm_model，使用默认值
        # 但这种情况不应该发生，因为 LLM 应该由分析流程传入
        provider = getattr(self.config, 'llm_provider', None) or "dashscope"
        model = getattr(self.config, 'llm_model', None)
        
        if not model:
            logger.warning(
                f"⚠️ Agent {self.agent_id} 的 config 中没有 llm_model，无法创建 LLM 客户端。"
                f"LLM 应该由分析流程（WorkflowBuilder）在创建 Agent 时传入，而不是从 Agent 配置中读取。"
            )
            return
        
        logger.warning(
            f"⚠️ Agent {self.agent_id} 正在从环境变量读取 API key 来创建 LLM 客户端。"
            f"这通常不应该发生，因为 LLM 应该由 WorkflowBuilder 在创建 Agent 时传入。"
            f"Provider: {provider}, Model: {model}"
        )
        
        self._llm_client = UnifiedLLMClient.from_provider(
            provider=provider,
            model=model,
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
            # 🔍 详细诊断：检查工具是否在注册表中
            has_metadata = registry.has_tool(tool_id)
            has_function = registry.get_function(tool_id) is not None
            
            if not has_metadata:
                logger.warning(
                    f"⚠️ [Agent {self.agent_id}] 工具未找到: {tool_id}\n"
                    f"   - 元数据: ❌ 不存在\n"
                    f"   - 函数: {'✅ 存在' if has_function else '❌ 不存在'}\n"
                    f"   💡 可能原因: 工具模块未加载或工具ID错误"
                )
            elif not has_function:
                logger.warning(
                    f"⚠️ [Agent {self.agent_id}] 工具未找到: {tool_id}\n"
                    f"   - 元数据: ✅ 存在\n"
                    f"   - 函数: ❌ 不存在\n"
                    f"   💡 可能原因: 工具函数未注册，请检查工具模块是否正确导入"
                )
                # 🔧 尝试重新加载工具模块
                try:
                    from core.tools.loader import get_tool_loader
                    loader = get_tool_loader()
                    if loader.load_tool(tool_id):
                        logger.info(f"🔄 [Agent {self.agent_id}] 已重新加载工具模块: {tool_id}")
                        # 重新尝试获取
                        tool = registry.get_langchain_tool(tool_id)
                        if tool:
                            self._langchain_tools.append(tool)
                            logger.info(f"✅ [Agent {self.agent_id}] 重新加载后成功获取工具: {tool_id}")
                            continue
                except Exception as e:
                    logger.debug(f"重新加载工具失败 {tool_id}: {e}")
            else:
                tool = registry.get_langchain_tool(tool_id)
                if tool:
                    self._langchain_tools.append(tool)
                    logger.info(f"✅ [Agent {self.agent_id}] 成功加载工具: {tool_id}")
                else:
                    logger.warning(
                        f"⚠️ [Agent {self.agent_id}] 工具元数据和函数存在，但无法创建 LangChain 工具: {tool_id}\n"
                        f"   - 元数据: ✅ 存在\n"
                        f"   - 函数: ✅ 存在\n"
                        f"   💡 可能原因: 函数格式不正确或 LangChain 工具创建失败"
                    )

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

            # 详细打印每条消息
            logger.info(f"=" * 100)
            logger.info(f"📋 [{self.agent_id}] 第 {iteration + 1} 次 LLM 调用 - 消息详情:")
            logger.info(f"=" * 100)
            for idx, msg in enumerate(current_messages):
                msg_type = type(msg).__name__
                if hasattr(msg, 'content'):
                    # 🔥 对于SystemMessage，打印完整内容以便验证模板是否正确
                    if msg_type == "SystemMessage":
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      🔍 完整内容: {msg.content}")
                    else:
                        content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      内容预览: {content_preview}")
                elif hasattr(msg, 'tool_calls'):
                    logger.info(f"  [{idx+1}] {msg_type}:")
                    logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                    for tc_idx, tc in enumerate(msg.tool_calls):
                        logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                else:
                    logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
            logger.info(f"=" * 100)

            # 🔥 添加重试机制（使用 agent 配置的 max_retries，默认3次）
            max_retries = getattr(self.config, 'max_retries', 3)
            retry_count = 0
            last_error = None
            
            while retry_count <= max_retries:
                try:
                    if retry_count > 0:
                        # 重试时等待（指数退避）
                        import time
                        wait_time = min(2 ** retry_count, 10)  # 最多等待10秒
                        logger.info(f"⏳ [{self.agent_id}] 等待 {wait_time} 秒后重试（第 {retry_count}/{max_retries} 次）...")
                        time.sleep(wait_time)
                        logger.info(f"🔄 [{self.agent_id}] 开始第 {retry_count} 次重试...")
                    
                    # 🔥 重试时使用原始的 self._llm，确保参数（temperature, max_tokens等）保留
                    if retry_count > 0:
                        # 重试时重新绑定工具（如果需要）
                        if self._langchain_tools:
                            llm_with_tools = self._llm.bind_tools(self._langchain_tools)
                            logger.info(f"🔗 [{self.agent_id}] 重试时重新绑定工具，保留原始LLM参数")
                        else:
                            llm_with_tools = self._llm
                            logger.info(f"🔗 [{self.agent_id}] 重试时使用原始LLM，保留所有参数")
                    
                    response = llm_with_tools.invoke(current_messages)
                    # 成功，跳出重试循环
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    last_error = e
                    
                    # 🔥 检查是否是 choices 为 null 的错误或其他可重试的错误
                    is_retryable = (
                        "choices" in error_msg.lower() or 
                        "null value" in error_msg.lower() or
                        "connection" in error_msg.lower() or
                        "timeout" in error_msg.lower() or
                        "rate limit" in error_msg.lower() or
                        "503" in error_msg or
                        "502" in error_msg or
                        "500" in error_msg
                    )
                    
                    if is_retryable and retry_count < max_retries:
                        retry_count += 1
                        logger.warning(f"⚠️ [{self.agent_id}] LLM 调用失败（可重试错误）: {error_msg}")
                        logger.warning(f"   将进行第 {retry_count}/{max_retries} 次重试...")
                        continue
                    else:
                        # 不可重试的错误或已达到最大重试次数
                        logger.error(f"❌ [{self.agent_id}] LLM API 调用失败")
                        logger.error(f"   错误信息: {error_msg}")
                        logger.error(f"   重试次数: {retry_count}/{max_retries}")
                        
                        if "choices" in error_msg.lower() or "null value" in error_msg.lower():
                            logger.error(f"   这可能是因为：")
                            logger.error(f"   1. LLM API 服务异常")
                            logger.error(f"   2. API 密钥无效或过期")
                            logger.error(f"   3. 请求参数不符合 API 要求")
                            logger.error(f"   4. API 服务暂时不可用")
                            # 🔥 尝试获取更多调试信息
                            if hasattr(self._llm, 'model_name'):
                                logger.error(f"   使用的模型: {self._llm.model_name}")
                            elif hasattr(self._llm, 'model'):
                                logger.error(f"   使用的模型: {self._llm.model}")
                            if hasattr(self._llm, 'openai_api_base'):
                                logger.error(f"   API Base: {self._llm.openai_api_base}")
                            elif hasattr(self._llm, 'base_url'):
                                logger.error(f"   API Base: {self._llm.base_url}")
                        
                        raise ValueError(f"LLM API 调用失败（已重试 {retry_count} 次）: {error_msg}") from last_error

            # 打印响应详情
            logger.info(f"=" * 100)
            logger.info(f"📤 [{self.agent_id}] LLM 响应详情:")
            logger.info(f"=" * 100)
            logger.info(f"  响应类型: {type(response).__name__}")
            if hasattr(response, 'content'):
                logger.info(f"  content 长度: {len(response.content)} 字符")
                logger.info(f"  content 预览: {response.content[:200] if response.content else '(空)'}")
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"  tool_calls 数量: {len(response.tool_calls)}")
                for tc_idx, tc in enumerate(response.tool_calls):
                    logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
            logger.info(f"=" * 100)
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
                    logger.info(f"📝 [{self.agent_id}] 添加分析提示词，长度: {len(analysis_prompt)} 字符")
                    current_messages.append(HumanMessage(content=analysis_prompt))
                else:
                    # 如果没有提供 analysis_prompt，添加默认的报告生成提示
                    logger.warning(f"⚠️ [{self.agent_id}] 未提供 analysis_prompt，使用默认提示")
                    default_prompt = """✅ 工具调用已完成，所有需要的数据都已获取。

🚫 **严格禁止再次调用工具**

📝 **现在请立即执行**：
基于上述工具返回的真实数据，按照之前的分析要求和输出格式，直接撰写完整的分析报告。

⚠️ **重要提醒**：
- 不要返回任何工具调用（tool_calls）
- 不要说"我需要调用工具"或"让我先获取数据"
- 直接输出中文分析报告内容

请立即开始撰写报告："""
                    current_messages.append(HumanMessage(content=default_prompt))

                # 再次调用 LLM（不绑定工具，强制生成报告）
                logger.info(f"📝 [{self.agent_id}] 工具执行完成，生成最终报告...")
                logger.info(f"📝 [{self.agent_id}] 当前消息数量: {len(current_messages)}")

                # 详细打印最终报告生成前的消息
                logger.info(f"=" * 100)
                logger.info(f"📋 [{self.agent_id}] 最终报告生成 - 消息详情:")
                logger.info(f"=" * 100)
                for idx, msg in enumerate(current_messages):
                    msg_type = type(msg).__name__
                    if hasattr(msg, 'content'):
                        content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      内容长度: {len(msg.content)} 字符")
                        logger.info(f"      内容预览: {content_preview}")
                    elif hasattr(msg, 'tool_calls'):
                        logger.info(f"  [{idx+1}] {msg_type}:")
                        logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                        for tc_idx, tc in enumerate(msg.tool_calls):
                            logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                    else:
                        logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
                logger.info(f"=" * 100)

                # 🔧 直接调用 LLM 生成报告（不绑定工具）
                # 注意：不使用 bind_tools([])，因为 DashScope 不接受空的 tools 数组
                logger.info(f"🔗 [{self.agent_id}] 直接调用 LLM 生成报告（无工具绑定）")
                
                # 🔥 添加重试机制（使用 agent 配置的 max_retries，默认3次）
                max_retries = getattr(self.config, 'max_retries', 3)
                retry_count = 0
                last_error = None
                
                while retry_count <= max_retries:
                    try:
                        if retry_count > 0:
                            # 重试时等待（指数退避）
                            import time
                            wait_time = min(2 ** retry_count, 10)  # 最多等待10秒
                            logger.info(f"⏳ [{self.agent_id}] 等待 {wait_time} 秒后重试生成报告（第 {retry_count}/{max_retries} 次）...")
                            time.sleep(wait_time)
                            logger.info(f"🔄 [{self.agent_id}] 开始第 {retry_count} 次重试生成报告...")
                        
                        # 🔥 使用原始的 self._llm，确保参数（temperature, max_tokens等）保留
                        final_response = self._llm.invoke(current_messages)
                        # 成功，跳出重试循环
                        break
                        
                    except Exception as e:
                        error_msg = str(e)
                        last_error = e
                        
                        # 🔥 检查是否是 choices 为 null 的错误或其他可重试的错误
                        is_retryable = (
                            "choices" in error_msg.lower() or 
                            "null value" in error_msg.lower() or
                            "connection" in error_msg.lower() or
                            "timeout" in error_msg.lower() or
                            "rate limit" in error_msg.lower() or
                            "503" in error_msg or
                            "502" in error_msg or
                            "500" in error_msg
                        )
                        
                        if is_retryable and retry_count < max_retries:
                            retry_count += 1
                            logger.warning(f"⚠️ [{self.agent_id}] 生成报告时 LLM 调用失败（可重试错误）: {error_msg}")
                            logger.warning(f"   将进行第 {retry_count}/{max_retries} 次重试...")
                            continue
                        else:
                            # 不可重试的错误或已达到最大重试次数
                            logger.error(f"❌ [{self.agent_id}] 生成报告时 LLM API 调用失败")
                            logger.error(f"   错误信息: {error_msg}")
                            logger.error(f"   重试次数: {retry_count}/{max_retries}")
                            
                            if "choices" in error_msg.lower() or "null value" in error_msg.lower():
                                logger.error(f"   这可能是因为：")
                                logger.error(f"   1. LLM API 服务异常")
                                logger.error(f"   2. API 密钥无效或过期")
                                logger.error(f"   3. 请求参数不符合 API 要求")
                                logger.error(f"   4. API 服务暂时不可用")
                                # 🔥 尝试获取更多调试信息
                                if hasattr(self._llm, 'model_name'):
                                    logger.error(f"   使用的模型: {self._llm.model_name}")
                                elif hasattr(self._llm, 'model'):
                                    logger.error(f"   使用的模型: {self._llm.model}")
                                if hasattr(self._llm, 'openai_api_base'):
                                    logger.error(f"   API Base: {self._llm.openai_api_base}")
                                elif hasattr(self._llm, 'base_url'):
                                    logger.error(f"   API Base: {self._llm.base_url}")
                            
                            raise ValueError(f"LLM API 调用失败（已重试 {retry_count} 次）: {error_msg}") from last_error

                # 打印最终响应详情
                logger.info(f"=" * 100)
                logger.info(f"📤 [{self.agent_id}] 最终报告响应详情:")
                logger.info(f"=" * 100)
                logger.info(f"  响应类型: {type(final_response).__name__}")
                if hasattr(final_response, 'content'):
                    logger.info(f"  content 长度: {len(final_response.content)} 字符")
                    logger.info(f"  content 预览: {final_response.content[:200] if final_response.content else '(空)'}")
                if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                    logger.info(f"  tool_calls 数量: {len(final_response.tool_calls)}")
                    for tc_idx, tc in enumerate(final_response.tool_calls):
                        logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                logger.info(f"=" * 100)

                # 检查是否还有 tool_calls（理论上不应该有，因为没有绑定工具）
                if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                    logger.warning(f"⚠️ [{self.agent_id}] 第二次调用仍返回 tool_calls: {len(final_response.tool_calls)} 个")
                    logger.warning(f"⚠️ [{self.agent_id}] LLM 没有理解指令，尝试添加更强烈的提示并重试")

                    # 添加更强烈的提示
                    retry_prompt = """🚨 **严重警告：你刚才返回了工具调用，这是错误的！**

❌ **禁止的行为**：
- 禁止返回任何 tool_calls
- 禁止说"我需要调用工具"
- 禁止说"让我先获取数据"

✅ **正确的行为**：
- 所有数据已经在上面的 ToolMessage 中
- 你现在唯一的任务是：撰写中文分析报告
- 直接输出报告文本内容

📝 **立即执行**：
基于上述工具返回的数据，按照之前的要求，直接撰写完整的分析报告。

现在开始撰写报告（只输出报告文本，不要有任何其他内容）："""
                    current_messages.append(HumanMessage(content=retry_prompt))

                    # 重试一次
                    logger.info(f"🔄 [{self.agent_id}] 重试生成报告...")

                    # 详细打印重试前的消息
                    logger.info(f"=" * 100)
                    logger.info(f"📋 [{self.agent_id}] 重试报告生成 - 消息详情:")
                    logger.info(f"=" * 100)
                    for idx, msg in enumerate(current_messages):
                        msg_type = type(msg).__name__
                        if hasattr(msg, 'content'):
                            content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                            logger.info(f"  [{idx+1}] {msg_type}:")
                            logger.info(f"      内容长度: {len(msg.content)} 字符")
                            logger.info(f"      内容预览: {content_preview}")
                        elif hasattr(msg, 'tool_calls'):
                            logger.info(f"  [{idx+1}] {msg_type}:")
                            logger.info(f"      工具调用数量: {len(msg.tool_calls)}")
                            for tc_idx, tc in enumerate(msg.tool_calls):
                                logger.info(f"        [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                        else:
                            logger.info(f"  [{idx+1}] {msg_type}: {str(msg)[:200]}")
                    logger.info(f"=" * 100)

                    # 🔧 重试时直接调用 LLM（不绑定工具）
                    logger.info(f"🔗 [{self.agent_id}] 重试时直接调用 LLM（无工具绑定）")
                    
                    # 🔥 添加重试机制（使用 agent 配置的 max_retries，默认3次）
                    max_retries = getattr(self.config, 'max_retries', 3)
                    retry_count = 0
                    last_error = None
                    
                    while retry_count <= max_retries:
                        try:
                            if retry_count > 0:
                                # 重试时等待（指数退避）
                                import time
                                wait_time = min(2 ** retry_count, 10)  # 最多等待10秒
                                logger.info(f"⏳ [{self.agent_id}] 等待 {wait_time} 秒后重试（第 {retry_count}/{max_retries} 次）...")
                                time.sleep(wait_time)
                                logger.info(f"🔄 [{self.agent_id}] 开始第 {retry_count} 次重试...")
                            
                            # 🔥 使用原始的 self._llm，确保参数（temperature, max_tokens等）保留
                            final_response = self._llm.invoke(current_messages)
                            # 成功，跳出重试循环
                            break
                            
                        except Exception as e:
                            error_msg = str(e)
                            last_error = e
                            
                            # 🔥 检查是否是 choices 为 null 的错误或其他可重试的错误
                            is_retryable = (
                                "choices" in error_msg.lower() or 
                                "null value" in error_msg.lower() or
                                "connection" in error_msg.lower() or
                                "timeout" in error_msg.lower() or
                                "rate limit" in error_msg.lower() or
                                "503" in error_msg or
                                "502" in error_msg or
                                "500" in error_msg
                            )
                            
                            if is_retryable and retry_count < max_retries:
                                retry_count += 1
                                logger.warning(f"⚠️ [{self.agent_id}] 重试时 LLM 调用失败（可重试错误）: {error_msg}")
                                logger.warning(f"   将进行第 {retry_count}/{max_retries} 次重试...")
                                continue
                            else:
                                # 不可重试的错误或已达到最大重试次数
                                logger.error(f"❌ [{self.agent_id}] 重试时 LLM API 调用失败")
                                logger.error(f"   错误信息: {error_msg}")
                                logger.error(f"   重试次数: {retry_count}/{max_retries}")
                                
                                if "choices" in error_msg.lower() or "null value" in error_msg.lower():
                                    logger.error(f"   这可能是因为：")
                                    logger.error(f"   1. LLM API 服务异常")
                                    logger.error(f"   2. API 密钥无效或过期")
                                    logger.error(f"   3. 请求参数不符合 API 要求")
                                    logger.error(f"   4. API 服务暂时不可用")
                                    # 🔥 尝试获取更多调试信息
                                    if hasattr(self._llm, 'model_name'):
                                        logger.error(f"   使用的模型: {self._llm.model_name}")
                                    elif hasattr(self._llm, 'model'):
                                        logger.error(f"   使用的模型: {self._llm.model}")
                                    if hasattr(self._llm, 'openai_api_base'):
                                        logger.error(f"   API Base: {self._llm.openai_api_base}")
                                    elif hasattr(self._llm, 'base_url'):
                                        logger.error(f"   API Base: {self._llm.base_url}")
                                
                                raise ValueError(f"LLM API 调用失败（已重试 {retry_count} 次）: {error_msg}") from last_error

                    # 打印重试响应详情
                    logger.info(f"=" * 100)
                    logger.info(f"📤 [{self.agent_id}] 重试响应详情:")
                    logger.info(f"=" * 100)
                    logger.info(f"  响应类型: {type(final_response).__name__}")
                    if hasattr(final_response, 'content'):
                        logger.info(f"  content 长度: {len(final_response.content)} 字符")
                        logger.info(f"  content 预览: {final_response.content[:200] if final_response.content else '(空)'}")
                    if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                        logger.info(f"  tool_calls 数量: {len(final_response.tool_calls)}")
                        for tc_idx, tc in enumerate(final_response.tool_calls):
                            logger.info(f"    [{tc_idx+1}] {tc.get('name', 'unknown')}: {tc.get('args', {})}")
                    logger.info(f"=" * 100)

                    # 再次检查
                    if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                        logger.error(f"❌ [{self.agent_id}] 重试后仍返回 tool_calls，放弃")
                        return "分析报告生成失败：LLM 持续返回工具调用而不是报告内容。请更换模型或重试。"

                content = final_response.content if hasattr(final_response, 'content') else str(final_response)
                logger.info(f"✅ [{self.agent_id}] 报告生成完成，长度: {len(content)} 字符")
                logger.debug(f"🔍 [{self.agent_id}] 报告内容预览: {content[:200] if content else '(空)'}")
                if not content or len(content.strip()) == 0:
                    logger.warning(f"⚠️ [{self.agent_id}] 报告内容为空！final_response类型: {type(final_response)}, hasattr content: {hasattr(final_response, 'content')}")
                    if hasattr(final_response, 'content'):
                        logger.warning(f"⚠️ [{self.agent_id}] final_response.content值: {repr(final_response.content)}")
                    # 检查是否有 tool_calls
                    if hasattr(final_response, 'tool_calls'):
                        logger.warning(f"⚠️ [{self.agent_id}] final_response.tool_calls: {final_response.tool_calls}")
                    # 打印完整的响应对象
                    logger.warning(f"⚠️ [{self.agent_id}] final_response完整对象: {final_response}")
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
                        logger.debug(f"🔍 [{self.agent_id}] 工具类型: {type(tool)}")
                        logger.debug(f"🔍 [{self.agent_id}] 工具 func: {getattr(tool, 'func', 'N/A')}")
                        
                        tool_result = tool.invoke(tool_args)
                        
                        # 🔥 检查返回的是否是协程对象（修复异步函数问题）
                        import asyncio
                        if asyncio.iscoroutine(tool_result):
                            logger.warning(f"⚠️ [{self.agent_id}] 工具 {tool_name} 返回协程对象，尝试等待完成...")
                            try:
                                # 尝试获取事件循环并等待协程
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    # 如果事件循环正在运行，需要在新线程中运行
                                    import threading
                                    result_container = {}
                                    exception_container = {}
                                    
                                    def run_coroutine():
                                        try:
                                            new_loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(new_loop)
                                            result_container['value'] = new_loop.run_until_complete(tool_result)
                                            new_loop.close()
                                        except Exception as e:
                                            exception_container['value'] = e
                                    
                                    thread = threading.Thread(target=run_coroutine, daemon=True)
                                    thread.start()
                                    thread.join(timeout=30)  # 30秒超时
                                    
                                    if thread.is_alive():
                                        raise TimeoutError("工具协程执行超时")
                                    if 'value' in exception_container:
                                        raise exception_container['value']
                                    tool_result = result_container.get('value')
                                else:
                                    tool_result = loop.run_until_complete(tool_result)
                            except RuntimeError:
                                # 没有事件循环，创建新的
                                tool_result = asyncio.run(tool_result)
                            logger.info(f"✅ [{self.agent_id}] 协程执行完成，结果类型: {type(tool_result).__name__}")

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

    def _get_prompt_from_template(
        self,
        agent_type: str,
        agent_name: str,
        variables: Dict[str, Any],
        context: Any = None,
        fallback_prompt: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
        prompt_type: str = "user"  # 🆕 新增参数：提示词类型（"user" 或 "system"）
    ) -> Optional[str]:
        """
        从模板系统获取提示词（通用方法）

        此方法被所有 Agent 基类共享，避免重复代码。
        自动从 state 中提取系统变量（如 current_price、industry 等）。

        Args:
            agent_type: Agent 类型（如 "analysts_v2", "researchers_v2", "managers_v2", "trader_v2"）
            agent_name: Agent 名称（如 "market_analyst_v2", "bull_researcher_v2"）
            variables: 模板变量字典
            context: AgentContext 对象（包含 user_id 和 preference_id）
            fallback_prompt: 降级提示词
            state: 工作流状态（可选，用于提取系统变量）
            prompt_type: 提示词类型（"user" 获取用户提示词，"system" 获取系统提示词）

        Returns:
            提示词文本，如果获取失败则返回 fallback_prompt
        """
        try:
            if prompt_type == "user":
                from tradingagents.utils.template_client import get_user_prompt as get_prompt_func
            else:
                from tradingagents.utils.template_client import get_agent_prompt as get_prompt_func
        except (ImportError, KeyError) as e:
            logger.warning(f"无法导入模板系统: {e}")
            return fallback_prompt

        try:
            # 🆕 自动从 state 中提取系统变量（由工作流引擎准备）
            if state:
                system_vars = [
                    "current_price", "industry", "market_name",
                    "currency_name", "currency_symbol", "current_date", "start_date"
                ]
                for var in system_vars:
                    if var in state and var not in variables:
                        variables[var] = state[var]
                        logger.info(f"📊 [系统变量] 自动提取 {var}: {state[var]}")

            # 从 context 中提取 user_id 和 preference_id
            user_id = None
            preference_id = "neutral"

            if context:
                # 🔍 诊断日志：打印 context 的类型和内容
                logger.info(f"🔍 [_get_prompt_from_template] context 类型: {type(context)}")
                if isinstance(context, dict):
                    logger.info(f"🔍 [_get_prompt_from_template] context 是字典，内容: {context}")
                    user_id = context.get("user_id")
                    preference_id = context.get("preference_id", "neutral")
                else:
                    logger.info(f"🔍 [_get_prompt_from_template] context 是对象，属性: {dir(context)}")
                    if hasattr(context, 'user_id'):
                        user_id = context.user_id
                    if hasattr(context, 'preference_id'):
                        preference_id = context.preference_id or "neutral"
                
                logger.info(f"🔍 [_get_prompt_from_template] 提取的 preference_id: {preference_id}, user_id: {user_id}")

            # 🔍 调试：打印传递给模板系统的变量
            logger.info(f"🔍 [_get_prompt_from_template] 准备传递给模板系统的变量 (共 {len(variables)} 个):")
            if not variables:
                logger.warning(f"⚠️ [_get_prompt_from_template] 变量字典为空！")
            else:
                for k, v in variables.items():
                    if isinstance(v, str) and len(v) > 100:
                        logger.info(f"  - {k}: {v[:100]}...")
                    else:
                        logger.info(f"  - {k}: {v}")
            
            # 🔍 诊断日志：打印传递给模板系统的参数
            logger.info(
                f"🔍 [_get_prompt_from_template] 调用模板系统参数: "
                f"agent_type={agent_type}, agent_name={agent_name}, "
                f"preference_id={preference_id}, user_id={user_id}, "
                f"variables数量={len(variables)}"
            )
            
            # 调用模板系统
            prompt = get_prompt_func(
                agent_type=agent_type,
                agent_name=agent_name,
                variables=variables,
                preference_id=preference_id,
                user_id=user_id,
                fallback_prompt=fallback_prompt,
                context=context
            )

            if prompt:
                logger.info(
                    f"✅ 从模板系统获取 {agent_name} {prompt_type} 提示词 "
                    f"(user_id={user_id}, preference_id={preference_id}, 长度={len(prompt)})"
                )
                # 🔍 诊断日志：打印提示词的前200字符，检查模板内容
                prompt_preview = prompt[:200] if len(prompt) > 200 else prompt
                logger.info(f"🔍 [_get_prompt_from_template] 提示词预览: {prompt_preview}")
                return prompt
            else:
                logger.warning(f"模板系统返回空提示词，使用降级提示词")
                return fallback_prompt

        except Exception as e:
            logger.warning(f"从模板系统获取提示词失败: {e}")
            return fallback_prompt

