# 模型使用验证指南

## 📋 概述

本文档说明如何验证前端传递的大模型配置是否真的被后端使用。

## 🔍 数据流追踪

### 1. 前端发送模型配置

**文件**：`frontend/src/views/Analysis/SingleAnalysis.vue`

```typescript
// 第 809-823 行
const request: SingleAnalysisRequest = {
  symbol: analysisForm.symbol,
  stock_code: analysisForm.symbol,
  parameters: {
    market_type: analysisForm.market,
    analysis_date: analysisDate.toISOString().split('T')[0],
    research_depth: getDepthDescription(analysisForm.researchDepth),
    selected_analysts: convertAnalystNamesToIds(analysisForm.selectedAnalysts),
    include_sentiment: analysisForm.includeSentiment,
    include_risk: analysisForm.includeRisk,
    language: analysisForm.language,
    quick_analysis_model: modelSettings.value.quickAnalysisModel,  // ✅ 传递快速模型
    deep_analysis_model: modelSettings.value.deepAnalysisModel     // ✅ 传递深度模型
  }
}
```

### 2. 后端接收模型配置

**文件**：`app/services/simple_analysis_service.py`

```python
# 第 734-767 行
# 1. 检查前端是否指定了模型
if (request.parameters and
    hasattr(request.parameters, 'quick_analysis_model') and
    hasattr(request.parameters, 'deep_analysis_model') and
    request.parameters.quick_analysis_model and
    request.parameters.deep_analysis_model):

    # ✅ 使用前端指定的模型
    quick_model = request.parameters.quick_analysis_model
    deep_model = request.parameters.deep_analysis_model

    logger.info(f"📝 [分析服务] 用户指定模型: quick={quick_model}, deep={deep_model}")

    # 验证模型是否合适
    validation = capability_service.validate_model_pair(
        quick_model, deep_model, research_depth
    )

    if not validation["valid"]:
        # 如果模型不合适，自动切换到推荐模型
        logger.info(f"🔄 自动切换到推荐模型...")
        quick_model, deep_model = capability_service.recommend_models_for_depth(
            research_depth
        )
        logger.info(f"✅ 已切换: quick={quick_model}, deep={deep_model}")
    else:
        logger.info(f"✅ 用户选择的模型验证通过: quick={quick_model}, deep={deep_model}")

else:
    # 2. 自动推荐模型
    quick_model, deep_model = capability_service.recommend_models_for_depth(
        research_depth
    )
    logger.info(f"🤖 自动推荐模型: quick={quick_model}, deep={deep_model}")
```

### 3. 创建分析配置

**文件**：`app/services/simple_analysis_service.py`

```python
# 第 776-797 行
# 创建分析配置
config = create_analysis_config(
    research_depth=research_depth,
    selected_analysts=request.parameters.selected_analysts if request.parameters else ["market", "fundamentals"],
    quick_model=quick_model,  # ✅ 传递快速模型
    deep_model=deep_model,    # ✅ 传递深度模型
    llm_provider="dashscope",
    market_type="A股"
)

# 🔍 验证配置中的模型
logger.info(f"🔍 [模型验证] 配置中的快速模型: {config.get('quick_think_llm')}")
logger.info(f"🔍 [模型验证] 配置中的深度模型: {config.get('deep_think_llm')}")
logger.info(f"🔍 [模型验证] 配置中的LLM供应商: {config.get('llm_provider')}")

# 初始化分析引擎
trading_graph = self._get_trading_graph(config)

# 🔍 验证TradingGraph实例中的配置
logger.info(f"🔍 [引擎验证] TradingGraph配置中的快速模型: {trading_graph.config.get('quick_think_llm')}")
logger.info(f"🔍 [引擎验证] TradingGraph配置中的深度模型: {trading_graph.config.get('deep_think_llm')}")
```

### 4. 配置函数处理

**文件**：`app/services/simple_analysis_service.py`

```python
# 第 127-311 行
def create_analysis_config(
    research_depth,
    selected_analysts: list,
    quick_model: str,  # ✅ 接收快速模型
    deep_model: str,   # ✅ 接收深度模型
    llm_provider: str,
    market_type: str = "A股"
) -> dict:
    # 从DEFAULT_CONFIG开始
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model      # ✅ 设置深度模型
    config["quick_think_llm"] = quick_model    # ✅ 设置快速模型

    # 根据研究深度调整配置
    if research_depth == "快速":
        logger.info(f"🔧 [1级-快速分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}")
    # ... 其他深度级别

    logger.info(f"📋 ========== 创建分析配置完成 ==========")
    logger.info(f"   ⚡ 快速模型: {config['quick_think_llm']}")
    logger.info(f"   🧠 深度模型: {config['deep_think_llm']}")
    logger.info(f"📋 ========================================")

    return config
```

### 5. TradingAgentsGraph 使用配置

**文件**：`app/services/simple_analysis_service.py`

```python
# 第 393-410 行
def _get_trading_graph(self, config: Dict[str, Any]) -> TradingAgentsGraph:
    """获取或创建TradingAgents实例"""
    config_key = str(sorted(config.items()))

    if config_key not in self._trading_graph_cache:
        logger.info(f"创建新的TradingAgents实例...")

        # ✅ 直接使用完整配置（包含模型信息）
        self._trading_graph_cache[config_key] = TradingAgentsGraph(
            selected_analysts=config.get("selected_analysts", ["market", "fundamentals"]),
            debug=config.get("debug", False),
            config=config  # ✅ 传递完整配置，包含 quick_think_llm 和 deep_think_llm
        )

        logger.info(f"✅ TradingAgents实例创建成功")

    return self._trading_graph_cache[config_key]
```

## 🧪 验证步骤

### 步骤 1：启动后端服务

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤 2：在前端选择模型

1. 打开单股分析页面
2. 在"模型设置"中选择：
   - 快速分析模型：`qwen-turbo`
   - 深度分析模型：`qwen-plus`
3. 选择分析深度：`3级 - 标准分析`
4. 输入股票代码：`000001`
5. 点击"开始分析"

### 步骤 3：查看后端日志

在后端终端中，你应该看到以下日志：

```
📝 [分析服务] 用户指定模型: quick=qwen-turbo, deep=qwen-plus
✅ 用户选择的模型验证通过: quick=qwen-turbo, deep=qwen-plus

📋 ========== 创建分析配置完成 ==========
   🎯 研究深度: 标准
   🔥 辩论轮次: 2
   ⚖️ 风险讨论轮次: 2
   💾 记忆功能: True
   🌐 在线工具: True
   🤖 LLM供应商: dashscope
   ⚡ 快速模型: qwen-turbo
   🧠 深度模型: qwen-plus
📋 ========================================

🔍 [模型验证] 配置中的快速模型: qwen-turbo
🔍 [模型验证] 配置中的深度模型: qwen-plus
🔍 [模型验证] 配置中的LLM供应商: dashscope

🔍 [引擎验证] TradingGraph配置中的快速模型: qwen-turbo
🔍 [引擎验证] TradingGraph配置中的深度模型: qwen-plus
```

### 步骤 4：验证模型实际调用

在分析过程中，你还会看到 TradingAgents 库的日志，显示实际调用的模型：

```
🤖 [LLM调用] 使用模型: qwen-turbo (快速分析)
🤖 [LLM调用] 使用模型: qwen-plus (深度分析)
```

## ✅ 验证结果

如果你看到以上日志，说明：

1. ✅ **前端成功传递**：模型配置从前端正确传递到后端
2. ✅ **后端成功接收**：后端正确解析并使用前端传递的模型
3. ✅ **配置成功创建**：分析配置中包含正确的模型信息
4. ✅ **引擎成功使用**：TradingAgentsGraph 实例使用了正确的模型配置
5. ✅ **模型实际调用**：分析过程中实际调用了指定的模型

## 🔧 故障排查

### 问题 1：日志显示"自动推荐模型"

**原因**：前端没有传递模型配置，或者传递的模型配置为空。

**解决方案**：
1. 检查前端 `modelSettings.value` 是否有值
2. 检查 API 请求中是否包含 `quick_analysis_model` 和 `deep_analysis_model`
3. 使用浏览器开发者工具查看网络请求

### 问题 2：日志显示"自动切换到推荐模型"

**原因**：前端传递的模型不满足分析深度要求（`validation["valid"]` 为 `false`）。

**解决方案**：
1. 查看验证警告日志，了解为什么模型不合适
2. 选择更高能力等级的模型
3. 或者降低分析深度

### 问题 3：配置中的模型与前端选择不一致

**原因**：可能是缓存问题或配置覆盖问题。

**解决方案**：
1. 重启后端服务
2. 清除浏览器缓存
3. 检查是否有其他地方覆盖了模型配置

## 📊 模型使用流程图

```
前端选择模型
    ↓
前端发送请求 (quick_analysis_model, deep_analysis_model)
    ↓
后端接收参数 (request.parameters.quick_analysis_model, request.parameters.deep_analysis_model)
    ↓
验证模型是否合适 (validate_model_pair)
    ↓
    ├─ 合适 → 使用用户选择的模型
    └─ 不合适 → 自动切换到推荐模型
    ↓
创建分析配置 (create_analysis_config)
    ↓
设置配置参数 (config["quick_think_llm"], config["deep_think_llm"])
    ↓
创建TradingGraph实例 (TradingAgentsGraph)
    ↓
执行分析 (trading_graph.propagate)
    ↓
实际调用LLM (使用配置中的模型)
```

## 🎯 总结

前端传递的大模型配置**确实被后端使用**，整个流程如下：

1. **前端传递**：`modelSettings.value.quickAnalysisModel` 和 `modelSettings.value.deepAnalysisModel`
2. **后端接收**：`request.parameters.quick_analysis_model` 和 `request.parameters.deep_analysis_model`
3. **验证模型**：检查模型是否适合当前分析深度
4. **创建配置**：将模型设置到 `config["quick_think_llm"]` 和 `config["deep_think_llm"]`
5. **初始化引擎**：TradingAgentsGraph 使用配置中的模型
6. **执行分析**：实际调用指定的模型进行分析

通过查看后端日志中的 🔍 标记，可以清楚地追踪模型配置在整个流程中的传递和使用情况。

