# 调试日志增强 - 2025-10-11

## 📋 问题背景

用户报告：
- **1级分析深度**：市场分析师正常调用统一工具 ✅
- **2级分析深度**：市场分析师出错，可能调用了错误的工具 ❌

关键差异：
- 1级深度：`quick_think_llm = qwen-turbo`, `deep_think_llm = qwen-plus`
- 2级深度：`quick_think_llm = qwen-plus`, `deep_think_llm = qwen-plus`

## 🎯 目标

添加详细的日志来追踪：
1. 使用的LLM模型
2. 绑定的工具列表
3. LLM返回的tool_calls
4. 条件判断的决策过程

## 📝 添加的日志

### 1. 市场分析师 (`market_analyst.py`)

#### 工具选择阶段
```python
logger.info(f"📊 [市场分析师] 使用统一市场数据工具，自动识别股票类型")
logger.info(f"📊 [市场分析师] 配置: online_tools={toolkit.config['online_tools']}")
logger.info(f"📊 [市场分析师] 绑定的工具: {tool_names_debug}")
logger.info(f"📊 [市场分析师] 目标市场: {market_info['market_name']}")
```

#### LLM调用阶段
```python
logger.info(f"📊 [市场分析师] LLM类型: {llm.__class__.__name__}")
logger.info(f"📊 [市场分析师] LLM模型: {getattr(llm, 'model_name', 'unknown')}")
logger.info(f"📊 [市场分析师] 消息历史数量: {len(state['messages'])}")
logger.info(f"📊 [市场分析师] 开始调用LLM...")
logger.info(f"📊 [市场分析师] LLM调用完成")
```

#### 结果检查阶段
```python
logger.info(f"📊 [市场分析师] 非Google模型 ({llm.__class__.__name__})，使用标准处理逻辑")
logger.info(f"📊 [市场分析师] 检查LLM返回结果...")
logger.info(f"📊 [市场分析师] - 是否有tool_calls: {hasattr(result, 'tool_calls')}")
if hasattr(result, 'tool_calls'):
    logger.info(f"📊 [市场分析师] - tool_calls数量: {len(result.tool_calls)}")
    if result.tool_calls:
        for i, tc in enumerate(result.tool_calls):
            logger.info(f"📊 [市场分析师] - tool_call[{i}]: {tc.get('name', 'unknown')}")
```

#### 分支处理阶段
```python
# 无工具调用
logger.info(f"📊 [市场分析师] ✅ 直接回复（无工具调用），长度: {len(report)}")

# 有工具调用
logger.info(f"📊 [市场分析师] 🔧 检测到工具调用: {[call.get('name', 'unknown') for call in result.tool_calls]}")
```

### 2. 基本面分析师 (`fundamentals_analyst.py`)

#### 工具选择阶段
```python
logger.info(f"📊 [基本面分析师] 使用统一基本面分析工具，自动识别股票类型")
logger.info(f"📊 [基本面分析师] 配置: online_tools={toolkit.config['online_tools']}")
logger.info(f"📊 [基本面分析师] 绑定的工具: {tool_names_debug}")
logger.info(f"📊 [基本面分析师] 目标市场: {market_info['market_name']}")
```

#### LLM调用阶段
```python
logger.info(f"📊 [基本面分析师] LLM类型: {fresh_llm.__class__.__name__}")
logger.info(f"📊 [基本面分析师] LLM模型: {getattr(fresh_llm, 'model_name', 'unknown')}")
logger.info(f"📊 [基本面分析师] 消息历史数量: {len(state['messages'])}")
logger.info(f"📊 [基本面分析师] ✅ 工具绑定成功，绑定了 {len(tools)} 个工具")
logger.info(f"📊 [基本面分析师] 开始调用LLM...")
logger.info(f"📊 [基本面分析师] LLM调用完成")
```

#### 结果检查阶段
```python
logger.info(f"📊 [基本面分析师] - 是否有tool_calls: {hasattr(result, 'tool_calls')}")
if hasattr(result, 'tool_calls'):
    logger.info(f"📊 [基本面分析师] - tool_calls数量: {len(result.tool_calls)}")
    if result.tool_calls:
        for i, tc in enumerate(result.tool_calls):
            logger.info(f"📊 [基本面分析师] - tool_call[{i}]: {tc.get('name', 'unknown')}")
```

### 3. 条件判断逻辑 (`conditional_logic.py`)

#### 市场分析师条件判断
```python
logger.info(f"🔀 [条件判断] should_continue_market")
logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
logger.info(f"🔀 [条件判断] - 报告长度: {len(market_report)}")
logger.info(f"🔀 [条件判断] - 最后消息类型: {type(last_message).__name__}")
logger.info(f"🔀 [条件判断] - 是否有tool_calls: {hasattr(last_message, 'tool_calls')}")
if hasattr(last_message, 'tool_calls'):
    logger.info(f"🔀 [条件判断] - tool_calls数量: {len(last_message.tool_calls) if last_message.tool_calls else 0}")
    if last_message.tool_calls:
        for i, tc in enumerate(last_message.tool_calls):
            logger.info(f"🔀 [条件判断] - tool_call[{i}]: {tc.get('name', 'unknown')}")

# 决策结果
logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Market")
# 或
logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_market")
# 或
logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear Market")
```

#### 基本面分析师条件判断
```python
logger.info(f"🔀 [条件判断] should_continue_fundamentals")
logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
logger.info(f"🔀 [条件判断] - 报告长度: {len(fundamentals_report)}")
logger.info(f"🔀 [条件判断] - 最后消息类型: {type(last_message).__name__}")
logger.info(f"🔀 [条件判断] - 是否有tool_calls: {hasattr(last_message, 'tool_calls')}")
if hasattr(last_message, 'tool_calls'):
    logger.info(f"🔀 [条件判断] - tool_calls数量: {len(last_message.tool_calls) if last_message.tool_calls else 0}")

# 决策结果
logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Fundamentals")
# 或
logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_fundamentals")
# 或
logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear Fundamentals")
```

## 📊 日志分析指南

### 正常流程的日志模式

#### 市场分析师正常流程
```
📊 [市场分析师] 使用统一市场数据工具，自动识别股票类型
📊 [市场分析师] 配置: online_tools=True
📊 [市场分析师] 绑定的工具: ['get_stock_market_data_unified']
📊 [市场分析师] 目标市场: 中国A股
📊 [市场分析师] LLM类型: ChatDashScopeOpenAI
📊 [市场分析师] LLM模型: qwen-turbo  # 或 qwen-plus
📊 [市场分析师] 消息历史数量: 1
📊 [市场分析师] 开始调用LLM...
📊 [市场分析师] LLM调用完成
📊 [市场分析师] 非Google模型 (ChatDashScopeOpenAI)，使用标准处理逻辑
📊 [市场分析师] 检查LLM返回结果...
📊 [市场分析师] - 是否有tool_calls: True
📊 [市场分析师] - tool_calls数量: 1
📊 [市场分析师] - tool_call[0]: get_stock_market_data_unified  # ✅ 正确
📊 [市场分析师] 🔧 检测到工具调用: ['get_stock_market_data_unified']
🔀 [条件判断] should_continue_market
🔀 [条件判断] - 消息数量: 2
🔀 [条件判断] - 报告长度: 0
🔀 [条件判断] - 最后消息类型: AIMessage
🔀 [条件判断] - 是否有tool_calls: True
🔀 [条件判断] - tool_calls数量: 1
🔀 [条件判断] - tool_call[0]: get_stock_market_data_unified
🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_market
# 工具执行...
🔀 [条件判断] should_continue_market
🔀 [条件判断] - 消息数量: 4
🔀 [条件判断] - 报告长度: 1500  # ✅ 报告已生成
🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Market
```

### 异常流程的日志模式

#### 错误的工具调用
```
📊 [市场分析师] 绑定的工具: ['get_stock_market_data_unified']
📊 [市场分析师] LLM模型: qwen-plus
📊 [市场分析师] - tool_call[0]: get_YFin_data  # ❌ 错误！调用了未绑定的工具
```

#### 死循环模式
```
# 第1次循环
📊 [市场分析师] 消息历史数量: 1
📊 [市场分析师] - tool_call[0]: get_stock_market_data_unified
🔀 [条件判断] - 报告长度: 0
🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_market

# 第2次循环
📊 [市场分析师] 消息历史数量: 3  # 增加了2条消息
📊 [市场分析师] - tool_call[0]: get_stock_market_data_unified  # ❌ 又调用了相同工具
🔀 [条件判断] - 报告长度: 0  # ❌ 报告仍然为空
🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_market

# 第3次循环
📊 [市场分析师] 消息历史数量: 5  # 继续增加
...
```

## 🔍 诊断步骤

### 步骤1：确认配置
查找日志：
```
📊 [市场分析师] 配置: online_tools=True
📊 [市场分析师] 绑定的工具: ['get_stock_market_data_unified']
```

### 步骤2：确认LLM模型
查找日志：
```
📊 [市场分析师] LLM类型: ChatDashScopeOpenAI
📊 [市场分析师] LLM模型: qwen-turbo  # 或 qwen-plus
```

### 步骤3：检查工具调用
查找日志：
```
📊 [市场分析师] - tool_call[0]: get_stock_market_data_unified
```

**如果工具名称不匹配绑定的工具，说明LLM调用了错误的工具！**

### 步骤4：检查循环次数
统计日志中 `should_continue_market` 或 `should_continue_fundamentals` 出现的次数。

**如果超过3次，说明进入了死循环！**

### 步骤5：检查报告生成
查找日志：
```
🔀 [条件判断] - 报告长度: 1500
```

**如果报告长度始终为0，说明报告没有生成！**

## 📈 预期效果

通过这些日志，我们可以：

1. **快速定位问题**：
   - 是配置问题？
   - 是LLM模型问题？
   - 是工具调用问题？
   - 是条件判断问题？

2. **对比不同深度**：
   - 1级深度使用 `qwen-turbo`
   - 2级深度使用 `qwen-plus`
   - 对比两者的工具调用行为

3. **追踪死循环**：
   - 消息数量持续增加
   - 报告长度始终为0
   - 重复调用相同工具

4. **验证修复效果**：
   - 修复后，日志应该显示正常流程
   - 报告长度应该 > 100
   - 循环次数应该 <= 2

## 🎯 下一步

1. **运行测试**：
   - 分别测试1级和2级深度
   - 收集完整日志

2. **对比分析**：
   - 对比两个深度的日志差异
   - 找出导致问题的关键差异

3. **实施修复**：
   - 根据日志分析结果
   - 实施针对性的修复方案

---

**创建日期**: 2025-10-11  
**创建人员**: AI Assistant  
**状态**: ✅ 已完成

