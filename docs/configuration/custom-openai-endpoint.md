# 自定义OpenAI端点使用指南

## 概述

TradingAgents现在支持自定义OpenAI兼容端点，允许您使用任何支持OpenAI API格式的服务，包括：

- 官方OpenAI API
- 第三方OpenAI代理服务
- 本地部署的模型（如Ollama、vLLM等）
- 其他兼容OpenAI格式的API服务

## 功能特性

✅ **完整集成**: 支持Web UI和CLI两种使用方式  
✅ **灵活配置**: 可自定义API端点URL和API密钥  
✅ **丰富模型**: 预置常用模型选项，支持自定义模型  
✅ **快速配置**: 提供常用服务的快速配置按钮  
✅ **统一接口**: 与其他LLM提供商使用相同的接口  

## Web UI使用方法

### 1. 选择提供商
在侧边栏的"LLM配置"部分，从下拉菜单中选择"🔧 自定义OpenAI端点"。

### 2. 配置端点
- **API端点URL**: 输入您的OpenAI兼容API端点
  - 官方OpenAI: `https://api.openai.com/v1`
  - DeepSeek: `https://api.deepseek.com/v1`
  - 本地服务: `http://localhost:8000/v1`
- **API密钥**: 输入对应的API密钥

### 3. 选择模型
从预置模型中选择，或选择"自定义模型"手动输入模型名称。

### 4. 快速配置
使用快速配置按钮一键设置常用服务：
- **官方OpenAI**: 自动设置官方API端点
- **中转服务**: 设置常用的API代理服务
- **本地部署**: 设置本地模型服务端点

## CLI使用方法

### 1. 启动CLI
```bash
python cli/main.py
```

### 2. 选择提供商
在LLM提供商选择界面，选择"🔧 自定义OpenAI端点"。

### 3. 配置端点
输入您的自定义OpenAI端点URL，例如：
- `https://api.openai.com/v1`
- `https://api.deepseek.com/v1`
- `http://localhost:8000/v1`

### 4. 选择模型
从可用模型列表中选择适合的模型。

## 环境变量配置

### 设置API密钥
在`.env`文件中添加：
```bash
CUSTOM_OPENAI_API_KEY=your_api_key_here
```

### 设置默认端点（可选）
```bash
CUSTOM_OPENAI_BASE_URL=https://api.openai.com/v1
```

## 支持的模型

### OpenAI官方模型
- `gpt-3.5-turbo`
- `gpt-4`
- `gpt-4-turbo`
- `gpt-4o`
- `gpt-4o-mini`

### Anthropic模型（通过代理）
- `claude-3-haiku`
- `claude-3-sonnet`
- `claude-3-opus`
- `claude-3.5-sonnet`

### 开源模型
- `llama-3.1-8b`
- `llama-3.1-70b`
- `llama-3.1-405b`

### Google模型（通过代理）
- `gemini-pro`
- `gemini-1.5-pro`

## 使用场景

### 1. 使用官方OpenAI API
```
端点: https://api.openai.com/v1
密钥: 您的OpenAI API密钥
模型: gpt-4o-mini
```

### 2. 使用第三方代理服务
```
端点: https://your-proxy-service.com/v1
密钥: 您的代理服务密钥
模型: gpt-4o
```

### 3. 使用本地部署模型
```
端点: http://localhost:8000/v1
密钥: 任意值（本地服务通常不需要）
模型: llama-3.1-8b
```

### 4. 使用DeepSeek API
```
端点: https://api.deepseek.com/v1
密钥: 您的DeepSeek API密钥
模型: deepseek-chat
```

### 5. 使用硅基流动（SiliconFlow）
```
端点: https://api.siliconflow.cn/v1
密钥: 您的SiliconFlow API密钥
模型: Qwen/Qwen2.5-7B-Instruct（免费）
```

硅基流动是一家专注于AI基础设施的服务商，提供：
- 🆓 **免费模型**: Qwen2.5-7B等多个模型免费使用
- 💰 **按量计费**: 灵活的定价方案
- 🔌 **OpenAI兼容**: 完全兼容OpenAI API格式
- 🚀 **高性能**: 优化的推理性能和低延迟

## 故障排除

### 常见问题

**Q: 连接失败怎么办？**
A: 检查端点URL是否正确，确保网络连接正常，验证API密钥是否有效。

**Q: 模型不可用怎么办？**
A: 确认您选择的模型在目标API服务中可用，或选择"自定义模型"手动输入。

**Q: 如何验证配置是否正确？**
A: 可以先进行一次简单的股票分析测试，查看是否能正常返回结果。

### 调试技巧

1. **检查日志**: 查看控制台输出的错误信息
2. **验证端点**: 使用curl或Postman测试API端点
3. **确认模型**: 查询API服务支持的模型列表
4. **网络检查**: 确保能访问目标API服务

## 技术实现

### 核心组件
- `ChatCustomOpenAI`: 自定义OpenAI适配器类
- `create_openai_compatible_llm`: 统一LLM创建工厂函数
- `OPENAI_COMPATIBLE_PROVIDERS`: 提供商配置字典

### 集成点
- **Web UI**: `web/components/sidebar.py`
- **CLI**: `cli/utils.py` 和 `cli/main.py`
- **核心逻辑**: `tradingagents/graph/trading_graph.py`
- **分析运行器**: `web/utils/analysis_runner.py`

## 更新日志

### v1.0.0 (2025-01-01)
- ✅ 添加自定义OpenAI端点支持
- ✅ 集成Web UI配置界面
- ✅ 集成CLI选择流程
- ✅ 支持多种预置模型
- ✅ 添加快速配置功能
- ✅ 完善错误处理和日志记录

---

如有问题或建议，请提交Issue或联系开发团队。