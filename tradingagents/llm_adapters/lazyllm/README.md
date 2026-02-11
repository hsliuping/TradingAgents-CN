# TradingAgents LazyLLM 适配器

基于 [LazyLLM](https://github.com/LazyAGI/LazyLLM) 的统一模型接入模块，为 TradingAgents 提供简化的 LLM 配置方式。

## 特性

- 🔧 **简化配置**: 使用 `TRADING_` 前缀的环境变量统一管理配置
- 🔌 **即插即用**: 不传参数时自动从环境变量读取配置
- 🔄 **LangChain 兼容**: 完全兼容现有的 LangChain ChatOpenAI 接口
- 🌐 **多供应商支持**: 支持 阿里云、DeepSeek、智谱、OpenAI 等主流模型

## 快速开始

### 1. 设置环境变量

```bash
# 阿里云通义千问 (推荐)
export TRADING_QWEN_API_KEY=sk-xxx

# 或其他供应商
export TRADING_DEEPSEEK_API_KEY=sk-xxx
export TRADING_ZHIPU_API_KEY=xxx.xxx
export TRADING_OPENAI_API_KEY=sk-xxx

# 可选：指定默认模型
export TRADING_DEFAULT_SOURCE=qwen
export TRADING_DEFAULT_MODEL=qwen-plus
```

### 2. 使用适配器

```python
from tradingagents.llm_adapters.lazyllm import create_trading_llm, TradingLLMAdapter

# 方式1: 使用便捷函数（推荐）
llm = create_trading_llm()
response = llm.invoke("分析一下贵州茅台的股票走势")
print(response.content)

# 方式2: 显式指定参数
llm = create_trading_llm(
    source="qwen",
    model="qwen-max",
    temperature=0.7
)

# 方式3: 直接使用类
llm = TradingLLMAdapter(
    source="deepseek",
    model="deepseek-chat"
)
```

## 支持的模型

| 供应商 | source | 默认模型 | 环境变量 |
|--------|--------|----------|----------|
| 阿里云通义 | `qwen` | qwen-plus | `TRADING_QWEN_API_KEY` |
| DeepSeek | `deepseek` | deepseek-chat | `TRADING_DEEPSEEK_API_KEY` |
| 智谱AI | `zhipu` | glm-4 | `TRADING_ZHIPU_API_KEY` |
| OpenAI | `openai` | gpt-3.5-turbo | `TRADING_OPENAI_API_KEY` |
| Kimi | `kimi` | moonshot-v1-8k | `TRADING_KIMI_API_KEY` |
| 豆包 | `doubao` | doubao-pro-32k | `TRADING_DOUBAO_API_KEY` |

## 环境变量优先级

适配器会按以下顺序查找 API Key：

1. 初始化时传入的 `api_key` 参数
2. `TRADING_{SOURCE}_API_KEY` 环境变量
3. 备用环境变量（兼容原有配置，如 `DASHSCOPE_API_KEY`）

## 配置选项

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `TRADING_DEFAULT_SOURCE` | 默认模型来源 | 自动检测可用的 |
| `TRADING_DEFAULT_MODEL` | 默认模型名称 | 根据来源决定 |
| `TRADING_TEMPERATURE` | 默认温度参数 | `0.1` |
| `TRADING_MAX_TOKENS` | 默认最大 token 数 | 无限制 |

## 模块结构

```
lazyllm/
├── __init__.py      # 模块入口
├── config.py        # 配置管理
├── adapter.py       # LangChain 适配器
├── automodel.py     # LazyLLM AutoModel 封装
├── test.py          # 测试脚本
└── README.md        # 本文档
```

## 与现有适配器的对比

| 特性 | 原有适配器 | LazyLLM 适配器 |
|------|-----------|----------------|
| 配置方式 | 每个供应商单独环境变量 | 统一 `TRADING_` 前缀 |
| 默认配置 | 需要显式指定 | 自动检测可用配置 |
| 模型切换 | 需要修改代码 | 修改环境变量即可 |
| LangChain 兼容 | ✅ | ✅ |

## 开发说明

### 运行测试

```bash
# 设置 API Key
export TRADING_QWEN_API_KEY=sk-xxx

# 运行测试
python -m tradingagents.llm_adapters.lazyllm.test
```

### 添加新供应商

1. 在 `config.py` 的 `TradingConfig` 类中添加：
   - `SUPPORTED_SOURCES` 列表
   - `DEFAULT_MODELS` 映射
   - `API_KEY_ENVS` 映射

2. 在 `adapter.py` 的 `_SOURCE_BASE_URLS` 字典中添加对应的 base_url

## 致谢

- [LazyLLM](https://github.com/LazyAGI/LazyLLM) - 提供统一的模型接入框架
- [LangChain](https://github.com/langchain-ai/langchain) - 提供 LLM 抽象接口
