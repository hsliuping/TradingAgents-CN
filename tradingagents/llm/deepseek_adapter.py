"""
DeepSeek V3 LLM适配器
支持工具调用和智能体创建
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.schema import BaseMessage
from langchain.tools import BaseTool
from langchain.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

class DeepSeekAdapter:
    """DeepSeek V3适配器类"""
    
    # 支持的模型列表（专注于最适合股票分析的模型）
    SUPPORTED_MODELS = {
        "deepseek-chat": "deepseek-chat",      # 通用对话模型，最适合股票投资分析
        # 注意：deepseek-coder 虽然支持工具调用，但专注于代码任务，不如通用模型适合投资分析
        # 注意：deepseek-reasoner 不支持工具调用，因此不包含在此列表中
    }
    
    # DeepSeek API基础URL
    BASE_URL = "https://api.deepseek.com"
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        base_url: Optional[str] = None
    ):
        """
        初始化DeepSeek V3适配器
        
        Args:
            api_key: DeepSeek API密钥
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", self.BASE_URL)
        
        if not self.api_key:
            raise ValueError("需要提供DEEPSEEK_API_KEY")
        
        # 获取实际模型名称
        self.model = self.SUPPORTED_MODELS.get(model, "deepseek-chat")
        
        # 初始化LangChain模型
        self._init_llm()
        
        logger.info(f"DeepSeek V3适配器初始化完成，模型: {self.model}")
    
    def _init_llm(self):
        """初始化LangChain LLM"""
        try:
            # 使用最新的LangChain OpenAI接口
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,  # 新版本使用api_key而不是openai_api_key
                base_url=self.base_url,  # 新版本使用base_url而不是openai_api_base
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                streaming=False
            )
            logger.info("LangChain ChatOpenAI (DeepSeek)初始化成功")
        except Exception as e:
            # 尝试使用旧版本的参数名
            try:
                self.llm = ChatOpenAI(
                    model=self.model,
                    openai_api_key=self.api_key,
                    openai_api_base=self.base_url,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    streaming=False
                )
                logger.info("LangChain ChatOpenAI (DeepSeek)初始化成功 - 使用兼容模式")
            except Exception as e2:
                logger.error(f"初始化DeepSeek模型失败: {e}")
                logger.error(f"兼容模式也失败: {e2}")
                raise e
    
    def create_agent(
        self, 
        tools: List[BaseTool], 
        system_prompt: str,
        max_iterations: int = 10,
        verbose: bool = False
    ) -> AgentExecutor:
        """
        创建支持工具调用的智能体
        
        Args:
            tools: 工具列表
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            verbose: 是否显示详细日志
            
        Returns:
            AgentExecutor: 智能体执行器
        """
        try:
            # 创建提示词模板
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}")
            ])
            
            # 创建智能体
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=tools,
                prompt=prompt
            )
            
            # 创建智能体执行器
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=max_iterations,
                verbose=verbose,
                return_intermediate_steps=True,
                handle_parsing_errors=True
            )
            
            logger.info(f"智能体创建成功，工具数量: {len(tools)}")
            return agent_executor
            
        except Exception as e:
            logger.error(f"创建智能体失败: {e}")
            raise
    
    def bind_tools(self, tools):
        """
        绑定工具到LLM
        
        Args:
            tools: 工具列表
            
        Returns:
            绑定了工具的LLM实例
        """
        return self.llm.bind_tools(tools)
    
    def chat(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> str:
        """
        直接聊天接口
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            str: 模型回复
        """
        try:
            response = self.llm.invoke(messages, **kwargs)
            return response.content
        except Exception as e:
            logger.error(f"聊天调用失败: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": "DeepSeek",
            "model": self.model,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "base_url": self.base_url,
            "supports_tools": True,
            "supports_streaming": False,
            "context_length": "128K" if "chat" in self.model else "64K"
        }
    
    @classmethod
    def get_available_models(cls) -> Dict[str, str]:
        """获取可用模型列表"""
        return cls.SUPPORTED_MODELS.copy()
    
    @staticmethod
    def is_available() -> bool:
        """检查DeepSeek是否可用"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        enabled = os.getenv("DEEPSEEK_ENABLED", "false").lower() == "true"
        
        return bool(api_key and enabled)
    
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            from langchain.schema import HumanMessage
            test_message = [HumanMessage(content="Hello, this is a test.")]
            response = self.chat(test_message)
            return bool(response)
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False


def create_deepseek_adapter(
    model: str = "deepseek-chat",
    temperature: float = 0.1,
    **kwargs
) -> DeepSeekAdapter:
    """
    便捷函数：创建DeepSeek适配器
    
    Args:
        model: 模型名称
        temperature: 温度参数
        **kwargs: 其他参数
        
    Returns:
        DeepSeekAdapter: DeepSeek适配器实例
    """
    return DeepSeekAdapter(
        model=model,
        temperature=temperature,
        **kwargs
    )


# 导出主要类和函数
__all__ = [
    "DeepSeekAdapter",
    "create_deepseek_adapter"
]
