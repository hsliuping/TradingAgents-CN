# Google AI 自定义 base_url 支持

## 📋 概述

本文档说明如何为 Google AI 配置自定义 API 端点（base_url），使其与其他 LLM 厂商（DashScope、DeepSeek、Ollama 等）保持一致的配置方式。

## 🎯 实现目标

1. ✅ Google AI 支持 `base_url` 参数
2. ✅ 与其他厂商保持一致的配置逻辑
3. ✅ 自动处理 `/v1` 和 `/v1beta` 路径差异
4. ✅ 支持自定义代理和私有部署

## 🔧 技术实现

### 1. 核心修改

#### `tradingagents/llm_adapters/google_openai_adapter.py`

```python
class ChatGoogleOpenAI(ChatGoogleGenerativeAI):
    def __init__(self, base_url: Optional[str] = None, **kwargs):
        """
        初始化 Google AI OpenAI 兼容客户端
        
        Args:
            base_url: 自定义 API 端点（可选）
                     例如：https://generativelanguage.googleapis.com/v1beta
                          https://generativelanguage.googleapis.com/v1
                          https://your-proxy.com
        """
        
        # 处理自定义 base_url
        if base_url:
            # 提取域名部分（移除 /v1 或 /v1beta 后缀）
            if base_url.endswith('/v1beta'):
                api_endpoint = base_url[:-8]
            elif base_url.endswith('/v1'):
                api_endpoint = base_url[:-3]
            else:
                api_endpoint = base_url
            
            # 通过 client_options 传递域名
            # SDK 会自动添加 /v1beta 路径
            kwargs["client_options"] = {"api_endpoint": api_endpoint}
        
        super().__init__(**kwargs)
```

**关键点**：
- `client_options.api_endpoint` 只需要域名部分
- Google AI SDK 会自动添加 `/v1beta/models/...` 等路径
- 如果传递完整路径会导致重复：`/v1beta/v1beta/`

#### `tradingagents/graph/trading_graph.py`

**修改 1：`create_llm_by_provider` 函数**

```python
if provider.lower() == "google":
    google_api_key = os.getenv('GOOGLE_API_KEY')
    if not google_api_key:
        raise ValueError("使用Google需要设置GOOGLE_API_KEY环境变量")

    return ChatGoogleOpenAI(
        model=model,
        google_api_key=google_api_key,
        base_url=backend_url if backend_url else None,  # ✅ 传递 base_url
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )
```

**修改 2：`TradingAgentsGraph.__init__` 方法**

```python
elif self.config["llm_provider"].lower() == "google":
    # 获取 backend_url
    backend_url = self.config.get("backend_url")
    
    self.deep_thinking_llm = ChatGoogleOpenAI(
        model=self.config["deep_think_llm"],
        google_api_key=google_api_key,
        base_url=backend_url if backend_url else None,  # ✅ 传递 base_url
        temperature=deep_temperature,
        max_tokens=deep_max_tokens,
        timeout=deep_timeout
    )
```

### 2. 配置方式

#### 数据库配置

**厂家配置（llm_providers 集合）**：

```json
{
    "name": "google",
    "display_name": "Google AI",
    "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_key_env_var": "GOOGLE_API_KEY",
    ...
}
```

**模型配置（llm_configs 集合）**：

```json
{
    "provider": "google",
    "model_name": "gemini-2.5-flash",
    "api_base": "https://your-custom-endpoint.com/v1beta",  // 可选，覆盖厂家配置
    ...
}
```

#### 配置优先级

```
模型配置的 api_base > 厂家配置的 default_base_url > SDK 默认端点
```

### 3. URL 处理逻辑

| 输入 base_url | 提取的域名 | SDK 最终请求 URL |
|--------------|-----------|-----------------|
| `https://generativelanguage.googleapis.com/v1beta` | `https://generativelanguage.googleapis.com` | `https://generativelanguage.googleapis.com/v1beta/models/...` |
| `https://generativelanguage.googleapis.com/v1` | `https://generativelanguage.googleapis.com` | `https://generativelanguage.googleapis.com/v1beta/models/...` |
| `https://your-proxy.com` | `https://your-proxy.com` | `https://your-proxy.com/v1beta/models/...` |

**说明**：
- 自动移除 `/v1` 或 `/v1beta` 后缀
- SDK 会自动添加 `/v1beta` 路径
- 避免路径重复问题

## 📝 使用示例

### 示例 1：使用默认端点

```python
from tradingagents.llm_adapters import ChatGoogleOpenAI

llm = ChatGoogleOpenAI(
    model="gemini-2.5-flash",
    google_api_key="YOUR_API_KEY"
)
# 使用默认端点：https://generativelanguage.googleapis.com
```

### 示例 2：使用自定义端点

```python
llm = ChatGoogleOpenAI(
    model="gemini-2.5-flash",
    google_api_key="YOUR_API_KEY",
    base_url="https://your-proxy.com/v1beta"
)
# 使用自定义端点：https://your-proxy.com
```

### 示例 3：通过工厂函数创建

```python
from tradingagents.graph.trading_graph import create_llm_by_provider

llm = create_llm_by_provider(
    provider="google",
    model="gemini-2.5-flash",
    backend_url="https://your-proxy.com/v1beta",
    temperature=0.7,
    max_tokens=2000,
    timeout=60
)
```

## 🧪 测试

运行测试脚本验证功能：

```bash
python scripts/test_google_base_url.py
```

**测试内容**：
1. ✅ 默认端点创建
2. ✅ 自定义端点（v1beta）创建
3. ✅ 自动转换 v1 到域名
4. ✅ create_llm_by_provider 函数传递 base_url

## 🔍 常见问题

### Q1: 为什么会出现 `/v1beta/v1beta/` 重复？

**原因**：`client_options.api_endpoint` 包含了完整路径（如 `/v1beta`），SDK 会自动添加 `/v1beta`，导致重复。

**解决**：只传递域名部分给 `client_options.api_endpoint`。

### Q2: 如何配置代理？

**方法 1：系统代理**（推荐）
- 使用 V2Ray 的系统代理模式
- 应用会自动使用系统代理

**方法 2：环境变量**
```bash
export HTTP_PROXY=http://127.0.0.1:10809
export HTTPS_PROXY=http://127.0.0.1:10809
```

**注意**：Google AI SDK 的 gRPC 模式不支持 HTTP 代理，建议使用 REST 模式：

```python
llm = ChatGoogleOpenAI(
    model="gemini-2.5-flash",
    transport="rest"  # 使用 REST 模式，支持 HTTP 代理
)
```

### Q3: 如何验证配置是否生效？

查看日志输出：

```
🔍 [Google初始化] 处理 base_url: https://generativelanguage.googleapis.com/v1beta
🔍 [Google初始化] 从 base_url 提取域名: https://generativelanguage.googleapis.com
✅ [Google初始化] 设置 client_options.api_endpoint: https://generativelanguage.googleapis.com
   SDK 会自动添加 /v1beta 路径
```

## 📚 参考资料

- [LangChain Google GenAI Issue #783](https://github.com/langchain-ai/langchain-google/issues/783)
- [Google AI Python SDK 文档](https://ai.google.dev/api/python/google/generativeai)
- [LangChain ChatGoogleGenerativeAI 文档](https://python.langchain.com/docs/integrations/chat/google_generative_ai)

## 🎉 总结

现在 Google AI 已经完全支持自定义 `base_url`，与其他 LLM 厂商保持一致的配置方式：

- ✅ 统一的配置接口
- ✅ 灵活的端点配置
- ✅ 自动路径处理
- ✅ 支持代理和私有部署

用户可以像配置其他厂商一样配置 Google AI，无需特殊处理。

