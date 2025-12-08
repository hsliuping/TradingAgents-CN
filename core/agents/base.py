"""
智能体基类

所有智能体都应继承此基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable

from .config import AgentMetadata, AgentConfig


class BaseAgent(ABC):
    """
    智能体基类
    
    提供统一的接口和通用功能:
    - LLM 调用
    - 工具管理
    - 提示词渲染
    - 状态管理
    - 日志记录
    """
    
    # 子类需要定义的元数据
    metadata: AgentMetadata = None
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._llm_client = None
        self._tools: Dict[str, Callable] = {}
        self._prompt_template: Optional[str] = None
    
    @classmethod
    def get_metadata(cls) -> AgentMetadata:
        """获取智能体元数据"""
        if cls.metadata is None:
            raise NotImplementedError(f"{cls.__name__} 必须定义 metadata")
        return cls.metadata
    
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
        """LLM 客户端"""
        return self._llm_client

