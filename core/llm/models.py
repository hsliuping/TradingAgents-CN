"""
LLM 相关数据模型定义
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    DASHSCOPE = "dashscope"  # 通义千问
    ZHIPU = "zhipu"          # 智谱AI
    SILICONFLOW = "siliconflow"  # 硅基流动
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """统一消息格式"""
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    tool_call_id: Optional[str] = None
    
    class Config:
        use_enum_values = True


class ToolCall(BaseModel):
    """工具调用定义"""
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def from_openai_format(cls, tool_call: dict) -> "ToolCall":
        """从 OpenAI 格式转换"""
        import json
        return cls(
            id=tool_call.get("id", ""),
            name=tool_call.get("function", {}).get("name", ""),
            arguments=json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        )
    
    @classmethod
    def from_google_format(cls, tool_call: dict) -> "ToolCall":
        """从 Google 格式转换"""
        return cls(
            id=tool_call.get("id", f"call_{hash(str(tool_call))}"),
            name=tool_call.get("name", ""),
            arguments=tool_call.get("args", {})
        )


class ToolResult(BaseModel):
    """工具执行结果"""
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.2  # 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
    max_tokens: Optional[int] = None
    timeout: int = 60
    
    # 高级配置
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    
    # 工具调用配置
    tool_choice: Optional[str] = None  # "auto", "none", "required"
    parallel_tool_calls: bool = True
    
    class Config:
        use_enum_values = True
    
    @classmethod
    def from_env(cls, provider: LLMProvider) -> "LLMConfig":
        """从环境变量创建配置"""
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        
        config_map = {
            LLMProvider.OPENAI: {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            },
            LLMProvider.DEEPSEEK: {
                "api_key": os.getenv("DEEPSEEK_API_KEY"),
                "base_url": "https://api.deepseek.com",
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            },
            LLMProvider.DASHSCOPE: {
                "api_key": os.getenv("DASHSCOPE_API_KEY"),
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": os.getenv("DASHSCOPE_MODEL", "qwen-plus"),
            },
            LLMProvider.ZHIPU: {
                "api_key": os.getenv("ZHIPU_API_KEY"),
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": os.getenv("ZHIPU_MODEL", "glm-4"),
            },
            LLMProvider.GOOGLE: {
                "api_key": os.getenv("GOOGLE_API_KEY"),
                "model": os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
            },
            LLMProvider.ANTHROPIC: {
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
                "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            },
        }
        
        if provider not in config_map:
            raise ValueError(f"不支持的提供商: {provider}")
        
        config_data = config_map[provider]
        api_key = config_data.get("api_key")
        
        # 🔥 检查 API key 是否存在，如果不存在则记录警告
        if not api_key:
            env_key_map = {
                LLMProvider.OPENAI: "OPENAI_API_KEY",
                LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
                LLMProvider.DASHSCOPE: "DASHSCOPE_API_KEY",
                LLMProvider.ZHIPU: "ZHIPU_API_KEY",
                LLMProvider.GOOGLE: "GOOGLE_API_KEY",
                LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            }
            expected_env_key = env_key_map.get(provider, "API_KEY")
            logger.warning(
                f"⚠️ 环境变量 {expected_env_key} 未设置，LLM 客户端可能无法正常工作。"
                f"Provider: {provider.value}, Model: {config_data.get('model', 'unknown')}"
            )
            logger.warning(
                f"💡 请确保已调用 bridge_config_to_env() 或手动设置环境变量 {expected_env_key}"
            )
        
        return cls(provider=provider, **config_data)


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    
    # 元数据
    model: Optional[str] = None
    provider: Optional[LLMProvider] = None
    usage: Optional[Dict[str, int]] = None
    
    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return len(self.tool_calls) > 0
    
    def to_message(self) -> Message:
        """转换为消息格式"""
        return Message(
            role=MessageRole.ASSISTANT,
            content=self.content,
            tool_calls=self.tool_calls if self.tool_calls else None
        )


# 更新前向引用
Message.model_rebuild()

