# 混合供应商模式文档

## 📋 功能说明

混合供应商模式允许您在同一个分析任务中使用来自**不同厂家**的模型：
- **快速模型**：用于大量的基础分析工作（9个Agent）
- **深度模型**：用于关键的决策环节（2个Agent：Research Manager 和 Risk Manager）

## 🎯 使用场景

### 场景 1：成本优化
- 快速模型：`qwen-plus`（阿里百炼，便宜快速）
- 深度模型：`gemini-2.5-pro`（Google，质量更高）

**优势**：
- ✅ 降低成本：大部分工作用便宜的模型
- ✅ 保证质量：关键决策用更强的模型
- ✅ 提高速度：快速模型响应更快

### 场景 2：网络优化
- 快速模型：`qwen-plus`（国内访问，无需代理）
- 深度模型：`gemini-2.5-pro`（国外模型，通过代理访问）

**优势**：
- ✅ 稳定性：大部分请求不依赖代理
- ✅ 质量：关键决策使用最强模型

### 场景 3：功能互补
- 快速模型：`deepseek-chat`（推理能力强）
- 深度模型：`qwen-max`（中文理解好）

## 🔧 配置方法

### 前端配置

在前端选择模型时，可以自由组合不同厂家的模型：

```javascript
{
  "quick_model": "qwen-plus",        // 阿里百炼
  "deep_model": "gemini-2.5-pro"     // Google
}
```

### 后端自动处理

后端会自动检测并处理混合模式：

1. **查询模型配置**：
   ```python
   quick_provider_info = get_provider_and_url_by_model_sync("qwen-plus")
   # 返回: {"provider": "dashscope", "backend_url": "https://dashscope.aliyuncs.com/api/v1"}
   
   deep_provider_info = get_provider_and_url_by_model_sync("gemini-2.5-pro")
   # 返回: {"provider": "google", "backend_url": "https://generativelanguage.googleapis.com/v1"}
   ```

2. **检测混合模式**：
   ```python
   if quick_provider != deep_provider:
       logger.info("✅ [混合模式] 快速模型和深度模型来自不同厂家")
   ```

3. **创建 LLM 实例**：
   ```python
   # 快速模型使用阿里百炼
   quick_thinking_llm = create_llm_by_provider(
       provider="dashscope",
       model="qwen-plus",
       backend_url="https://dashscope.aliyuncs.com/api/v1",
       ...
   )
   
   # 深度模型使用 Google
   deep_thinking_llm = create_llm_by_provider(
       provider="google",
       model="gemini-2.5-pro",
       backend_url="https://generativelanguage.googleapis.com/v1",
       ...
   )
   ```

## 📊 Agent 使用情况

### 使用快速模型的 Agent（9个）

1. **Market Analyst（市场分析师）**
   - 作用：分析市场趋势、行业动态
   - 频率：每次分析都会调用

2. **Fundamentals Analyst（基本面分析师）**
   - 作用：分析财务数据、公司基本面
   - 频率：每次分析都会调用

3. **Technical Analyst（技术分析师）**
   - 作用：分析技术指标、K线形态
   - 频率：每次分析都会调用

4. **Bull Researcher（多头研究员）**
   - 作用：收集看涨观点
   - 频率：辩论阶段调用

5. **Bear Researcher（空头研究员）**
   - 作用：收集看跌观点
   - 频率：辩论阶段调用

6. **Trader（交易员）**
   - 作用：提出交易建议
   - 频率：每次分析都会调用

7. **Risky Analyst（激进分析师）**
   - 作用：评估高风险场景
   - 频率：风险评估阶段调用

8. **Neutral Analyst（中性分析师）**
   - 作用：评估中性场景
   - 频率：风险评估阶段调用

9. **Safe Analyst（保守分析师）**
   - 作用：评估低风险场景
   - 频率：风险评估阶段调用

### 使用深度模型的 Agent（2个）

1. **Research Manager（研究经理）**
   - 作用：综合多个分析师的报告，做出最终的投资判断
   - 频率：每次分析都会调用
   - 重要性：⭐⭐⭐⭐⭐（最关键）

2. **Risk Manager（风险管理器）**
   - 作用：评估投资风险，给出风险管理建议
   - 频率：每次分析都会调用
   - 重要性：⭐⭐⭐⭐⭐（最关键）

## 🧪 测试示例

### 示例 1：阿里百炼 + Google

```bash
# 前端选择
快速模型: qwen-plus
深度模型: gemini-2.5-pro

# 后端日志
🔍 [供应商查找] 快速模型 qwen-plus 对应的供应商: dashscope
🔍 [API地址] 快速模型使用 backend_url: https://dashscope.aliyuncs.com/api/v1
🔍 [供应商查找] 深度模型 gemini-2.5-pro 对应的供应商: google
🔍 [API地址] 深度模型使用 backend_url: https://generativelanguage.googleapis.com/v1
✅ [混合模式] 快速模型(dashscope) 和 深度模型(google) 来自不同厂家
🔀 [混合模式] 检测到不同厂家的模型组合
   快速模型: qwen-plus (dashscope)
   深度模型: gemini-2.5-pro (google)
✅ [混合模式] LLM 实例创建成功
```

### 示例 2：DeepSeek + 阿里百炼

```bash
# 前端选择
快速模型: deepseek-chat
深度模型: qwen-max

# 后端日志
🔍 [供应商查找] 快速模型 deepseek-chat 对应的供应商: deepseek
🔍 [API地址] 快速模型使用 backend_url: https://api.deepseek.com
🔍 [供应商查找] 深度模型 qwen-max 对应的供应商: dashscope
🔍 [API地址] 深度模型使用 backend_url: https://dashscope.aliyuncs.com/api/v1
✅ [混合模式] 快速模型(deepseek) 和 深度模型(dashscope) 来自不同厂家
```

### 示例 3：同一厂家（非混合模式）

```bash
# 前端选择
快速模型: qwen-plus
深度模型: qwen-max

# 后端日志
🔍 [供应商查找] 快速模型 qwen-plus 对应的供应商: dashscope
🔍 [API地址] 快速模型使用 backend_url: https://dashscope.aliyuncs.com/api/v1
🔍 [供应商查找] 深度模型 qwen-max 对应的供应商: dashscope
🔍 [API地址] 深度模型使用 backend_url: https://dashscope.aliyuncs.com/api/v1
✅ [供应商验证] 两个模型来自同一厂家: dashscope
```

## 💰 成本对比

### 方案 1：全部使用 Google 模型
```
快速模型: gemini-2.5-flash ($0.075/1M tokens)
深度模型: gemini-2.5-pro ($1.25/1M tokens)

假设一次分析：
- 快速模型调用 9 次，每次 2000 tokens = 18000 tokens
- 深度模型调用 2 次，每次 4000 tokens = 8000 tokens

成本 = (18000 * 0.075 + 8000 * 1.25) / 1000000 = $0.0114
```

### 方案 2：混合模式（推荐）
```
快速模型: qwen-plus ($0.004/1K tokens)
深度模型: gemini-2.5-pro ($1.25/1M tokens)

假设一次分析：
- 快速模型调用 9 次，每次 2000 tokens = 18000 tokens
- 深度模型调用 2 次，每次 4000 tokens = 8000 tokens

成本 = (18000 * 0.004 + 8000 * 1.25) / 1000000 = $0.0101
节省约 11%
```

### 方案 3：全部使用阿里百炼
```
快速模型: qwen-plus ($0.004/1K tokens)
深度模型: qwen-max ($0.04/1K tokens)

假设一次分析：
- 快速模型调用 9 次，每次 2000 tokens = 18000 tokens
- 深度模型调用 2 次，每次 4000 tokens = 8000 tokens

成本 = (18000 * 0.004 + 8000 * 0.04) / 1000000 = $0.0004
最便宜！
```

## ⚠️ 注意事项

### 1. API Key 配置

确保在 `.env` 文件中配置了所有需要的 API Key：

```bash
# Google
GOOGLE_API_KEY=your-google-api-key

# 阿里百炼
DASHSCOPE_API_KEY=your-dashscope-api-key

# DeepSeek
DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 2. 代理配置

如果使用 Google 模型，需要配置代理：

```bash
# V2RayN 代理
HTTP_PROXY=http://127.0.0.1:10809
HTTPS_PROXY=http://127.0.0.1:10809
```

### 3. 模型兼容性

所有模型都必须支持：
- ✅ 工具调用（Tool Calling）
- ✅ 流式输出（Streaming）
- ✅ 系统提示（System Prompt）

## 🎯 推荐组合

### 最佳性价比
```
快速模型: qwen-plus (阿里百炼)
深度模型: qwen-max (阿里百炼)
```

### 最佳质量
```
快速模型: gemini-2.5-flash (Google)
深度模型: gemini-2.5-pro (Google)
```

### 平衡方案
```
快速模型: qwen-plus (阿里百炼)
深度模型: gemini-2.5-pro (Google)
```

## 📅 更新日期

2025-10-12

