# 统一 LLM 客户端设计

## 📋 概述

当前系统有 7 种 LLM 适配器，代码重复严重。统一 LLM 客户端的目标是：
1. 提供统一的调用接口
2. 标准化工具调用格式
3. 屏蔽各 LLM 的差异
4. 减少维护成本

---

## 🔄 现有适配器分析

| 适配器 | 文件 | 特殊处理 |
|--------|------|----------|
| OpenAI | langchain_openai | 标准格式 |
| DeepSeek | deepseek_adapter.py | OpenAI 兼容 |
| DashScope | dashscope_openai_adapter.py | 工具调用格式不同 |
| Google | google_openai_adapter.py | 工具调用需特殊处理 |
| Anthropic | langchain_anthropic | 工具格式不同 |
| 智谱 | zhipu_adapter.py | OpenAI 兼容 |
| SiliconFlow | 使用 ChatOpenAI | OpenAI 兼容 |

---

## 🏗️ 统一架构

```
┌─────────────────────────────────────────────────────────────┐
│                    UnifiedLLMClient                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  invoke(messages, tools) -> LLMResponse             │    │
│  │  stream(messages, tools) -> AsyncIterator           │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    ToolCallNormalizer                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  normalize_request(tools) -> provider_format        │    │
│  │  normalize_response(raw) -> StandardToolCall        │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    Provider Adapters                         │
│  ┌───────────┬───────────┬───────────┬─────────────────┐    │
│  │  OpenAI   │  Google   │ Anthropic │ OpenAI-Compat   │    │
│  │  Adapter  │  Adapter  │  Adapter  │    Adapter      │    │
│  └───────────┴───────────┴───────────┴─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 核心数据模型

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

class ToolCall(BaseModel):
    """标准化工具调用"""
    id: str
    name: str
    arguments: Dict[str, Any]

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class Message(BaseModel):
    """标准化消息"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: List[ToolCall] = []

class LLMResponse(BaseModel):
    """标准化 LLM 响应"""
    content: str
    tool_calls: List[ToolCall] = []
    usage: Dict[str, int] = {}
    model: str = ""
    finish_reason: str = ""
    
class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str           # openai, google, anthropic, deepseek, dashscope, zhipu, siliconflow
    model: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
```

---

## 🔧 核心类实现

### UnifiedLLMClient

```python
class UnifiedLLMClient:
    """统一 LLM 客户端"""
    
    PROVIDER_MAP = {
        "openai": OpenAIAdapter,
        "google": GoogleAdapter,
        "anthropic": AnthropicAdapter,
        "deepseek": OpenAICompatAdapter,
        "dashscope": DashScopeAdapter,
        "zhipu": OpenAICompatAdapter,
        "siliconflow": OpenAICompatAdapter,
    }
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.adapter = self._create_adapter(config)
        self.normalizer = ToolCallNormalizer(config.provider)
    
    def _create_adapter(self, config: LLMConfig) -> BaseAdapter:
        """创建对应的适配器"""
        adapter_class = self.PROVIDER_MAP.get(config.provider)
        if not adapter_class:
            raise ValueError(f"Unknown provider: {config.provider}")
        return adapter_class(config)
    
    def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """同步调用"""
        # 1. 标准化工具定义
        normalized_tools = self.normalizer.normalize_tools(tools) if tools else None
        
        # 2. 调用适配器
        raw_response = self.adapter.invoke(messages, normalized_tools)
        
        # 3. 标准化响应
        return self.normalizer.normalize_response(raw_response)
    
    async def ainvoke(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """异步调用"""
        normalized_tools = self.normalizer.normalize_tools(tools) if tools else None
        raw_response = await self.adapter.ainvoke(messages, normalized_tools)
        return self.normalizer.normalize_response(raw_response)
```

### ToolCallNormalizer

```python
class ToolCallNormalizer:
    """工具调用标准化器"""
    
    def __init__(self, provider: str):
        self.provider = provider
    
    def normalize_tools(self, tools: List[Dict]) -> List[Dict]:
        """将标准工具定义转换为特定提供商格式"""
        if self.provider == "anthropic":
            return self._to_anthropic_format(tools)
        elif self.provider == "google":
            return self._to_google_format(tools)
        else:
            return self._to_openai_format(tools)
    
    def normalize_response(self, raw_response: Any) -> LLMResponse:
        """将各提供商响应转换为标准格式"""
        if self.provider == "google":
            return self._from_google_response(raw_response)
        elif self.provider == "anthropic":
            return self._from_anthropic_response(raw_response)
        else:
            return self._from_openai_response(raw_response)
    
    def _from_google_response(self, raw) -> LLMResponse:
        """Google 响应标准化 (处理特殊的工具调用格式)"""
        tool_calls = []
        if hasattr(raw, 'tool_calls') and raw.tool_calls:
            for tc in raw.tool_calls:
                # Google 的工具调用格式转换
                tool_calls.append(ToolCall(
                    id=tc.get('id', str(uuid.uuid4())),
                    name=tc.get('name') or tc.get('function', {}).get('name'),
                    arguments=tc.get('args') or tc.get('function', {}).get('arguments', {})
                ))
        return LLMResponse(
            content=raw.content or "",
            tool_calls=tool_calls,
            model=getattr(raw, 'model', ''),
        )
```

---

## 📊 迁移策略

1. **阶段 1**: 创建 UnifiedLLMClient，与现有适配器并存
2. **阶段 2**: 逐步迁移各分析师使用新客户端
3. **阶段 3**: 弃用旧适配器，标记为 deprecated
4. **阶段 4**: 删除旧适配器代码

