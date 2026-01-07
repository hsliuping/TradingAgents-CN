# Bug 修复：index_analyst_v2 返回空报告

## 🐛 问题描述

**日期**: 2026-01-07  
**版本**: v1.0.1  
**Agent**: `index_analyst_v2`

### 错误日志

```
2026-01-07 11:24:04 | core.agents.base     | INFO     | ✅ [index_analyst_v2] 报告生成完成，长度: 0 字符
2026-01-07 11:24:04 | core.agents.base     | WARNING  | ⚠️ [index_analyst_v2] 报告内容为空！final_response类型: <class 'langchain_core.messages.ai.AIMessage'>, hasattr content: True
2026-01-07 11:24:04 | core.agents.base     | WARNING  | ⚠️ [index_analyst_v2] final_response.content值: '''
```

### 症状

- `index_analyst_v2` Agent 执行完成，但返回的报告内容为空字符串
- LLM 返回的 `AIMessage.content` 是空字符串 `''`
- 工具调用成功，但 LLM 没有基于工具结果生成报告

---

## 🔍 根本原因分析

### 问题链路

1. **`AnalystAgent.execute()` 方法**（`core/agents/analyst.py`）:
   ```python
   # 第 124 行
   report = self.invoke_with_tools(messages)  # ❌ 没有传递 analysis_prompt
   ```

2. **`BaseAgent.invoke_with_tools()` 方法**（`core/agents/base.py`）:
   ```python
   # 第 345-347 行
   if analysis_prompt:
       current_messages.append(HumanMessage(content=analysis_prompt))
   ```
   - 如果没有 `analysis_prompt`，LLM 在工具执行后不知道要做什么
   - LLM 可能返回空内容或简单的确认信息

3. **工具调用流程**:
   ```
   1. LLM 调用工具（get_index_data, get_market_breadth）
   2. 工具返回数据
   3. 数据添加到消息历史
   4. 再次调用 LLM（没有明确的分析指令）
   5. LLM 返回空内容 ❌
   ```

### 为什么会返回空内容？

- **缺少明确指令**: LLM 在工具执行后没有收到"请基于工具结果生成报告"的指令
- **上下文不清晰**: LLM 不知道应该输出什么格式的内容
- **模型行为**: 某些 LLM 模型在没有明确指令时可能返回空内容

---

## ✅ 解决方案

### 修改文件

**文件**: `core/agents/analyst.py`

### 修改内容

**修改前**:
```python
if self._langchain_tools:
    logger.info(f"[{self.agent_id}] 使用工具调用模式，工具数量: {len(self._langchain_tools)}")
    logger.info(f"[{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")
    report = self.invoke_with_tools(messages)  # ❌ 没有 analysis_prompt
```

**修改后**:
```python
if self._langchain_tools:
    logger.info(f"[{self.agent_id}] 使用工具调用模式，工具数量: {len(self._langchain_tools)}")
    logger.info(f"[{self.agent_id}] 工具列表: {[tool.name for tool in self._langchain_tools]}")
    
    # 构建分析提示词，明确告诉 LLM 基于工具结果生成报告
    analysis_prompt = """现在请基于上述工具返回的数据，撰写详细的中文分析报告。

请确保报告内容：
1. 基于真实数据进行分析
2. 结构清晰，逻辑严谨
3. 结论明确，有理有据
4. 使用中文输出

请立即开始撰写报告。"""
    
    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)  # ✅ 传递 analysis_prompt
```

### 修改后的流程

```
1. LLM 调用工具（get_index_data, get_market_breadth）
2. 工具返回数据
3. 数据添加到消息历史
4. 添加 analysis_prompt 到消息历史 ✅
5. 再次调用 LLM（明确要求生成报告）
6. LLM 返回详细的分析报告 ✅
```

---

## 🎯 影响范围

### 受影响的 Agent

所有继承自 `AnalystAgent` 且使用工具调用的 Agent：

- ✅ `index_analyst_v2` - 大盘分析师
- ✅ `fundamentals_analyst_v2` - 基本面分析师
- ✅ `news_analyst_v2` - 新闻分析师
- ✅ `sector_analyst_v2` - 板块分析师
- ✅ `social_analyst_v2` - 社交媒体分析师
- ✅ 其他所有 v2.0 分析师

### 不受影响的 Agent

- ✅ `market_analyst_v2` - 已经正确传递了 `analysis_prompt`
- ✅ 不使用工具的 Agent（直接调用 LLM）

---

## 🧪 测试验证

### 测试步骤

1. **创建测试任务**:
   ```python
   from app.services.task_analysis_service import get_task_analysis_service
   from app.models.analysis import AnalysisTaskType
   from app.models.user import PyObjectId
   
   task_service = get_task_analysis_service()
   
   task = await task_service.create_task(
       user_id=PyObjectId("user_id"),
       task_type=AnalysisTaskType.STOCK_ANALYSIS,
       task_params={
           "symbol": "000001",
           "stock_code": "000001",
           "market_type": "cn",
           "analysis_date": "2026-01-07",
           "research_depth": 3
       },
       engine_type="workflow"
   )
   ```

2. **执行任务**:
   ```python
   await task_service.execute_task(task.task_id)
   ```

3. **检查日志**:
   ```
   ✅ [index_analyst_v2] 报告生成完成，长度: 1234 字符  # 不再是 0
   ```

4. **查看报告**:
   - 前往"分析报告"页面
   - 查看大盘分析部分
   - 确认内容不为空

### 预期结果

- ✅ `index_analyst_v2` 返回非空报告
- ✅ 报告内容基于工具返回的真实数据
- ✅ 报告格式清晰，逻辑严谨
- ✅ 没有警告日志

---

## 📚 相关代码

### 核心文件

- `core/agents/analyst.py` - AnalystAgent 基类
- `core/agents/base.py` - BaseAgent 基类（invoke_with_tools 方法）
- `core/agents/adapters/index_analyst_v2.py` - 大盘分析师 v2.0

### 相关方法

- `AnalystAgent.execute()` - 执行分析
- `BaseAgent.invoke_with_tools()` - 工具调用循环
- `BaseAgent._execute_tool_calls()` - 执行工具调用

---

## 💡 最佳实践

### 使用 `invoke_with_tools` 的正确方式

```python
# ✅ 正确：传递 analysis_prompt
analysis_prompt = """请基于上述工具返回的数据，撰写详细的分析报告。"""
report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)

# ❌ 错误：不传递 analysis_prompt
report = self.invoke_with_tools(messages)
```

### 为什么需要 `analysis_prompt`？

1. **明确指令**: 告诉 LLM 在工具执行后要做什么
2. **格式控制**: 指定报告的格式和结构
3. **质量保证**: 确保 LLM 输出符合预期
4. **避免空内容**: 防止 LLM 返回空字符串或无关内容

---

**最后更新**: 2026-01-07  
**修复版本**: v1.0.1  
**修复人**: TradingAgents-CN Pro Team

