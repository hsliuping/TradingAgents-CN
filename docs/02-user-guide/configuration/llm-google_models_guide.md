# Google AI 模型使用指南

## 经过验证的模型列表

基于实际测试结果，以下6个模型已验证可用：

### 1. gemini-2.5-flash-lite-preview-06-17 ⚡
- **平均响应时间**: 1.45秒
- **推荐用途**: 超快响应、实时交互、高频调用
- **适合场景**: 快速分析、实时问答、简单任务

### 2. gemini-2.0-flash 🚀
- **平均响应时间**: 1.87秒
- **推荐用途**: 快速响应、实时分析
- **适合场景**: 日常分析、快速决策

### 3. gemini-1.5-pro ⚖️
- **平均响应时间**: 2.25秒
- **推荐用途**: 平衡性能、复杂分析
- **适合场景**: 标准分析、专业任务

### 4. gemini-2.5-flash ⚡
- **平均响应时间**: 2.73秒
- **推荐用途**: 通用快速模型
- **适合场景**: 通用分析、高频使用

### 5. gemini-1.5-flash 💨
- **平均响应时间**: 2.87秒
- **推荐用途**: 备用快速模型
- **适合场景**: 简单分析、备用选择

### 6. gemini-2.5-pro 🧠
- **平均响应时间**: 16.68秒
- **推荐用途**: 功能强大、复杂推理
- **适合场景**: 深度分析、复杂任务、高质量输出

## 使用建议

### 按分析深度选择模型

1. **快速分析 (1级)**:
   - 快速模型: `gemini-2.5-flash-lite-preview-06-17`
   - 深度模型: `gemini-2.0-flash`

2. **基础分析 (2级)**:
   - 快速模型: `gemini-2.0-flash`
   - 深度模型: `gemini-1.5-pro`

3. **标准分析 (3级)**:
   - 快速模型: `gemini-1.5-pro`
   - 深度模型: `gemini-2.5-flash`

4. **深度分析 (4级)**:
   - 快速模型: `gemini-2.5-flash`
   - 深度模型: `gemini-2.5-pro`

5. **全面分析 (5级)**:
   - 快速模型: `gemini-2.5-pro`
   - 深度模型: `gemini-2.5-pro`

### 按使用场景选择模型

- **实时交互**: `gemini-2.5-flash-lite-preview-06-17`
- **快速决策**: `gemini-2.0-flash`
- **平衡分析**: `gemini-1.5-pro`
- **深度思考**: `gemini-2.5-pro`

## 配置示例

```python
# 快速配置
config = {
    "llm_provider": "google",
    "quick_think_llm": "gemini-2.5-flash-lite-preview-06-17",
    "deep_think_llm": "gemini-2.0-flash"
}

# 平衡配置
config = {
    "llm_provider": "google", 
    "quick_think_llm": "gemini-1.5-pro",
    "deep_think_llm": "gemini-2.5-flash"
}

# 强力配置
config = {
    "llm_provider": "google",
    "quick_think_llm": "gemini-2.5-flash",
    "deep_think_llm": "gemini-2.5-pro"
}
```

## 注意事项

1. 所有模型都支持Function Calling
2. 响应时间基于实际测试，可能因网络和负载而变化
3. 建议根据具体需求选择合适的模型组合
4. 对于成本敏感的应用，优先使用快速模型
