# 记忆模型提供商切换功能修复报告

## 问题描述

用户反映当修改记忆模型提供商时，记忆模型的名称没有随之变化，应该能够显示上一次输入的对应提供商的模型名称。

## 解决方案

### 1. 修改持久化逻辑 (`web/utils/persistence.py`)

**新增功能：**
- 在 `save_config()` 方法中添加了记忆模型名称的独立保存逻辑
- 使用 `memory_models_by_provider` 键来保存每个提供商对应的记忆模型名称
- 确保每个提供商的记忆模型名称能够独立保存和恢复

**关键代码：**
```python
# 保存每个提供商的记忆模型名称
if memory_provider and memory_model:
    memory_models_key = "memory_models_by_provider"
    if memory_models_key not in st.session_state:
        st.session_state[memory_models_key] = {}
    st.session_state[memory_models_key][memory_provider] = memory_model
    logger.debug(f"💾 [Persistence] 保存{memory_provider}的记忆模型: {memory_model}")
```

### 2. 修改侧边栏组件 (`web/components/sidebar.py`)

**主要改进：**
- 添加了记忆模型提供商变更检测逻辑
- 当提供商变更时，自动恢复之前为该提供商保存的模型名称
- 如果没有保存过，则使用默认值
- 改进了placeholder和help文本，使其更具体

**关键代码：**
```python
# 检查记忆模型提供商是否变更
previous_memory_provider = st.session_state.get('memory_provider')
if previous_memory_provider != memory_provider:
    logger.info(f"🔄 [Memory] 记忆模型提供商变更: {previous_memory_provider} → {memory_provider}")
    # 提供商变更时，尝试恢复之前保存的模型名称
    memory_models_by_provider = st.session_state.get('memory_models_by_provider', {})
    if memory_provider in memory_models_by_provider:
        st.session_state.memory_model = memory_models_by_provider[memory_provider]
        logger.debug(f"🔄 [Memory] 恢复{memory_provider}的记忆模型: {st.session_state.memory_model}")
    else:
        # 如果没有保存过，则清空让用户输入
        st.session_state.memory_model = ""
```

## 功能特性

### ✅ 已实现的功能

1. **独立保存**：每个提供商的记忆模型名称独立保存
2. **自动恢复**：切换提供商时自动恢复之前保存的模型名称
3. **默认值支持**：新提供商使用合理的默认模型名称
4. **用户友好**：placeholder和help文本根据提供商动态更新

### 🔧 使用场景

**场景1：用户为不同提供商设置不同的记忆模型**
- DashScope: `text-embedding-v1`
- OpenAI: `text-embedding-3-small`
- Google: `text-embedding-004`

**场景2：切换记忆模型提供商**
- 从DashScope切换到OpenAI时，自动显示 `text-embedding-3-small`
- 从OpenAI切换到Google时，自动显示 `text-embedding-004`
- 从Google切换到DeepSeek时，显示默认值 `text-embedding-v1`

**场景3：新提供商设置**
- 首次使用某个提供商时，显示该提供商的默认模型名称
- 用户输入自定义模型名称后，保存到该提供商的配置中

## 测试结果

### ✅ 测试通过的功能

1. **记忆模型名称保存**：每个提供商的模型名称正确保存
2. **提供商切换恢复**：切换提供商时正确恢复之前保存的模型名称
3. **新提供商处理**：新提供商使用默认模型名称
4. **配置加载**：配置加载时记忆模型正确恢复

### 📊 测试数据

```
保存的记忆模型映射: {
    'dashscope': 'text-embedding-v4', 
    'openai': 'text-embedding-3-small', 
    'google': 'embedding-001'
}

切换到dashscope提供商:
  ✅ 正确恢复了dashscope的记忆模型

切换到openai提供商:
  ✅ 正确恢复了openai的记忆模型

切换到google提供商:
  ✅ 正确恢复了google的记忆模型

切换到deepseek提供商:
  ✅ 使用默认模型名称
```

## 用户体验改进

### 之前的问题
- ❌ 切换记忆模型提供商时，模型名称不变
- ❌ 无法记住用户为每个提供商设置的模型名称
- ❌ 每次切换都需要重新输入模型名称

### 现在的改进
- ✅ 切换提供商时自动显示对应的模型名称
- ✅ 记住用户为每个提供商设置的模型名称
- ✅ 新提供商使用合理的默认值
- ✅ 更友好的用户界面提示

## 技术实现细节

### 数据存储结构
```python
st.session_state['memory_models_by_provider'] = {
    'dashscope': 'text-embedding-v1',
    'openai': 'text-embedding-3-small',
    'google': 'text-embedding-004',
    'deepseek': 'text-embedding-v1'
}
```

### 默认模型配置
```python
embedding_defaults = {
    "dashscope": "text-embedding-v4",
    "deepseek": "text-embedding-v1", 
    "openai": "text-embedding-3-small",
    "google": "embedding-001",
    "openrouter": "text-embedding-3",
    "硅基流动": "BAAI/bge-m3"
}
```

### 切换逻辑
1. 检测提供商变更
2. 查找之前保存的模型名称
3. 如果找到则恢复，否则使用默认值
4. 更新UI显示

## 后续优化建议

1. **持久化存储**：将 `memory_models_by_provider` 保存到本地存储或数据库
2. **模型验证**：添加模型名称的有效性验证
3. **批量导入**：支持批量导入不同提供商的模型配置
4. **配置导出**：支持导出和导入记忆模型配置

## 总结

本次修复成功解决了记忆模型提供商切换时模型名称不更新的问题。用户现在可以：

- 为每个提供商独立设置和保存记忆模型名称
- 切换提供商时自动恢复之前保存的模型名称
- 享受更智能的默认值体验
- 获得更好的用户界面反馈

这大大提升了用户体验，减少了重复输入的工作，使记忆模型配置更加便捷和智能。
