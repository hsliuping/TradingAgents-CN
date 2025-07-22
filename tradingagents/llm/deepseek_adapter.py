"""
DeepSeek V3 LLM adapter
Supports tool calls and agent creation
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
    """DeepSeek V3 adapter class"""
    
    # Supported model list (focused on models best suited for stock analysis)
    SUPPORTED_MODELS = {
        "deepseek-chat": "deepseek-chat",      # General conversation model, best suited for stock investment analysis
        # Note: deepseek-coder supports tool calls, but is focused on code tasks, not as suitable for investment analysis
        # Note: deepseek-reasoner does not support tool calls, so it is not included in this list
    }
    
    # DeepSeek API base URL
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
        Initialize DeepSeek V3 adapter
        
        Args:
            api_key: DeepSeek API key
            model: Model name
            temperature: Temperature parameter
            max_tokens: Maximum token count
            base_url: API base URL
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", self.BASE_URL)
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY must be provided")
        
        # Get actual model name
        self.model = self.SUPPORTED_MODELS.get(model, "deepseek-chat")
        
        # Initialize LangChain model
        self._init_llm()
        
        logger.info(f"DeepSeek V3 adapter initialized, model: {self.model}")
    
    def _init_llm(self):
        """Initialize LangChain LLM"""
        try:
            # Use the latest LangChain OpenAI interface
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,  # New version uses api_key instead of openai_api_key
                base_url=self.base_url,  # New version uses base_url instead of openai_api_base
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                streaming=False
            )
            logger.info("LangChain ChatOpenAI (DeepSeek) initialized successfully")
        except Exception as e:
            # Try using the old parameter names
            try:
                self.llm = ChatOpenAI(
                    model=self.model,
                    openai_api_key=self.api_key,
                    openai_api_base=self.base_url,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    streaming=False
                )
                logger.info("LangChain ChatOpenAI (DeepSeek) initialized successfully - using compatible mode")
            except Exception as e2:
                logger.error(f"Failed to initialize DeepSeek model: {e}")
                logger.error(f"Compatible mode also failed: {e2}")
                raise e
    
    def create_agent(
        self, 
        tools: List[BaseTool], 
        system_prompt: str,
        max_iterations: int = 10,
        verbose: bool = False
    ) -> AgentExecutor:
        """
        Create an agent supporting tool calls
        
        Args:
            tools: List of tools
            system_prompt: System prompt
            max_iterations: Maximum iterations
            verbose: Whether to show detailed logs
            
        Returns:
            AgentExecutor: Agent executor
        """
        try:
            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}")
            ])
            
            # Create agent
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=tools,
                prompt=prompt
            )
            
            # Create agent executor
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=max_iterations,
                verbose=verbose,
                return_intermediate_steps=True,
                handle_parsing_errors=True
            )
            
            logger.info(f"Agent created successfully, number of tools: {len(tools)}")
            return agent_executor
            
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            raise
    
    def chat(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> str:
        """
        Direct chat interface
        
        Args:
            messages: List of messages
            **kwargs: Other parameters
            
        Returns:
            str: Model response
        """
        try:
            response = self.llm.invoke(messages, **kwargs)
            return response.content
        except Exception as e:
            logger.error(f"Chat call failed: {e}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
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
        """Get available model list"""
        return cls.SUPPORTED_MODELS.copy()
    
    @staticmethod
    def is_available() -> bool:
        """Check if DeepSeek is available"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        enabled = os.getenv("DEEPSEEK_ENABLED", "false").lower() == "true"
        
        return bool(api_key and enabled)
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            from langchain.schema import HumanMessage
            test_message = [HumanMessage(content="Hello, this is a test.")]
            response = self.chat(test_message)
            return bool(response)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def create_deepseek_adapter(
    model: str = "deepseek-chat",
    temperature: float = 0.1,
    **kwargs
) -> DeepSeekAdapter:
    """
    Convenient function: Create DeepSeek adapter
    
    Args:
        model: Model name
        temperature: Temperature parameter
        **kwargs: Other parameters
        
    Returns:
        DeepSeekAdapter: DeepSeek adapter instance
    """
    return DeepSeekAdapter(
        model=model,
        temperature=temperature,
        **kwargs
    )


# Export main classes and functions
__all__ = [
    "DeepSeekAdapter",
    "create_deepseek_adapter"
]
