# 调试模板系统使用指南

## 快速开始

### 调试接口地址

```
POST http://127.0.0.1:3000/api/templates/debug/analyst
```

### 基本请求格式

```json
{
  "analyst_type": "fundamentals",
  "template_id": "6919a866fa8b760161a9167c",
  "use_current": false,
  "llm": {
    "provider": "dashscope",
    "model": "qwen-plus",
    "temperature": 0.2,
    "max_tokens": 4000,
    "backend_url": ""
  },
  "stock": {
    "symbol": "000001",
    "analysis_date": "2025-11-17"
  }
}
```

## 参数说明

### 必填参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `analyst_type` | string | 分析师类型 | `fundamentals`, `market`, `news`, `social` |
| `stock.symbol` | string | 股票代码 | `000001`, `AAPL`, `0700.HK` |
| `llm.provider` | string | LLM提供商 | `dashscope`, `openai`, `deepseek` |
| `llm.model` | string | 模型名称 | `qwen-plus`, `gpt-4o-mini` |

### 可选参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `template_id` | string | 调试模板ID | 无 |
| `llm.temperature` | float | 温度参数（股票分析推荐：0.2-0.3快速分析，0.1-0.2深度分析） | 0.2 |
| `llm.max_tokens` | int | 最大token数 | 4000 |
| `llm.backend_url` | string | API端点 | 根据provider自动设置 |
| `stock.analysis_date` | string | 分析日期 | 当前日期 |

## 使用场景

### 场景1: 测试新模板

当你创建了一个新的模板但还没有设为当前使用模板时，可以用调试接口测试：

```json
{
  "analyst_type": "fundamentals",
  "template_id": "新模板的ObjectId",
  "llm": {
    "provider": "dashscope",
    "model": "qwen-plus",
    "backend_url": ""
  },
  "stock": {
    "symbol": "000001"
  }
}
```

**工作流程**:
1. 调试接口检测到 `template_id` 存在
2. 自动设置 `is_debug_mode=true`
3. Agent 优先使用指定的调试模板
4. 不影响当前使用的模板

### 场景2: 测试不同的LLM提供商

```json
{
  "analyst_type": "fundamentals",
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "backend_url": ""
  },
  "stock": {
    "symbol": "AAPL"
  }
}
```

**支持的提供商**:
- `dashscope` - 阿里百炼
- `openai` - OpenAI
- `deepseek` - DeepSeek
- `google` - Google AI
- `anthropic` - Anthropic

### 场景3: 自定义API端点

```json
{
  "analyst_type": "fundamentals",
  "llm": {
    "provider": "dashscope",
    "model": "qwen-plus",
    "backend_url": "https://custom-api.example.com/v1"
  },
  "stock": {
    "symbol": "000001"
  }
}
```

## 响应格式

### 成功响应

```json
{
  "status": "success",
  "analyst_type": "fundamentals",
  "report": "分析报告内容...",
  "decision": {
    "action": "buy",
    "confidence": 0.85,
    "reasoning": "..."
  }
}
```

### 错误响应

```json
{
  "status": "error",
  "error": "错误信息",
  "detail": "详细错误说明"
}
```

## 调试技巧

### 1. 查看详细日志

调试接口会打印详细的日志，包括：
- 请求参数
- 最终配置
- AgentContext 参数
- LLM 调用信息
- 模板选择过程

### 2. 验证模板是否被使用

在日志中查找以下信息：

```
🔍 [调试模式] 使用调试模板ID: 6919a866fa8b760161a9167c
✅ [调试模式] 成功获取调试模板: analysts/fundamentals_analyst
```

### 3. 验证LLM配置

在日志中查找：

```
🔍 [DashScope调用] 即将调用 LLM API
   模型: qwen-plus
   API Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
   API Key: 有值
```

## 常见问题

### Q: 调试模板不存在怎么办？

A: 系统会自动降级到正常流程，使用用户模板或系统模板。查看日志中的降级信息。

### Q: 如何确认使用了正确的LLM提供商？

A: 查看日志中的 "API Base URL" 字段，确认是否为预期的URL。

### Q: 调试模式会影响当前使用的模板吗？

A: 不会。调试模式只在当前请求中生效，不会修改任何配置。

## 相关文档

- [调试模板系统修复总结](../analysis/DEBUG_TEMPLATE_SYSTEM_FIX.md)
- [模板系统设计文档](../design/v1.0.1/01_SYSTEM_DESIGN.md)
- [Agent集成指南](../development/AGENT_INTEGRATION_GUIDE.md)

