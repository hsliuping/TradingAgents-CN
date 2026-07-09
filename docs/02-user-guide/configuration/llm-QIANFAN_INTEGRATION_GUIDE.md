# 百度千帆模型接入指南

## 📋 概述

本指南专门针对百度千帆（文心一言）模型的接入过程，结合项目的最新实现，提供“OpenAI 兼容模式”的推荐用法，并保留“原生 AK/SK + Access Token”方式的历史说明（仅供参考）。

## 🎯 推荐接入模式：OpenAI 兼容（仅需 QIANFAN_API_KEY）

- 使用统一的 OpenAI 兼容适配器，无需 AK/SK 获取 Access Token。
- 只需要配置一个环境变量：QIANFAN_API_KEY（格式一般以 bce-v3/ 开头）。
- 统一走 openai-compatible 基座，支持 function calling、上下文长度、工具绑定等核心能力。

### 环境变量
```bash
# .env 文件
QIANFAN_API_KEY=bce-v3/ALTAK-xxxx/xxxx
```

### 代码入口（适配器）
- 适配器类：ChatQianfanOpenAI（位于 openai_compatible_base.py 内部注册）
- 基础地址：https://qianfan.baidubce.com/v2
- Provider 名称：qianfan

示例：
```python
from tradingagents.llm_adapters.openai_compatible_base import create_openai_compatible_llm

llm = create_openai_compatible_llm(
    provider="qianfan",
    model="ernie-3.5-8k",
    temperature=0.1,
    max_tokens=800
)

resp = llm.invoke("你好，简单自我介绍一下")
print(resp.content)
```

### 千帆常见模型（兼容模式）
- ernie-3.5-8k（默认）
- ernie-4.0-turbo-8k
- ERNIE-Speed-8K
- ERNIE-Lite-8K

> 提示：模型名称需与 openai_compatible_base.py 中的 qianfan 映射保持一致。

### 定价与计费（pricing.json）
- 已在 config/pricing.json 中新增 qianfan/ERNIE 系列占位价格，可在 Web 配置页调整。

## 🧰 可选：原生 AK/SK + Access Token（历史说明）
- 如需对接历史脚本或某些特定 API，可使用 AK/SK 方式获取 Access Token。
- 项目主路径已不再依赖 AK/SK，仅保留在脚本示例中（.env.example 注明为可选）。

参考流程（仅示意，不再作为默认路径）：
```python
import os, requests
api_key = os.getenv("QIANFAN_API_KEY")
secret_key = os.getenv("QIANFAN_SECRET_KEY")
url = "https://aip.baidubce.com/oauth/2.0/token"
params = {"grant_type":"client_credentials","client_id":api_key,"client_secret":secret_key}
r = requests.post(url, params=params, timeout=30)
print(r.json())
```

## 🧪 测试与验证

- 连接测试：确保 QIANFAN_API_KEY 已设置并能正常返回内容。
- 工具调用：通过 bind_tools 验证 function calling 在千帆上正常工作。

示例：
```python
from langchain_core.tools import tool
from tradingagents.llm_adapters.openai_compatible_base import create_openai_compatible_llm

@tool
def get_stock_price(symbol: str) -> str:
    return f"股票 {symbol} 的当前价格是 $150.00"

llm = create_openai_compatible_llm(provider="qianfan", model="ernie-3.5-8k")
llm_tools = llm.bind_tools([get_stock_price])
res = llm_tools.invoke("请查询 AAPL 的价格")
print(res.content)
```

## 🔧 故障排查
- QIANFAN_API_KEY 未设置或格式不正确（应以 bce-v3/ 开头）。
- 网络或限流问题：稍后重试，或降低并发。
- 模型名不在映射列表：参考 openai_compatible_base.py 的 qianfan 条目。

## 📚 相关文件
- tradingagents/llm_adapters/openai_compatible_base.py（核心适配器与 provider 映射）
- tradingagents/graph/trading_graph.py（运行时 provider 选择与校验）
- config/pricing.json（定价配置，可在 Web 中调整）
- .env.example（环境变量示例）