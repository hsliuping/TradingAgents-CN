# 研究深度一致性修复

## 📋 问题描述

用户发现前后端对于分析深度的表示不一致：

- **前端显示**：1级 - 快速分析、2级 - 基础分析、3级 - 标准分析、4级 - 深度分析、5级 - 全面分析
- **后端报告**：`"research_depth": "快速"`（中文字符串）
- **问题**：批量分析页面直接传递数字字符串（"1", "2", "3"），没有转换为中文

## 🔍 根本原因

### 1. 单股分析页面（正确）

<augment_code_snippet path="frontend/src/views/Analysis/SingleAnalysis.vue" mode="EXCERPT">
````typescript
research_depth: getDepthDescription(analysisForm.researchDepth),
````
</augment_code_snippet>

✅ 使用 `getDepthDescription()` 函数将数字转换为中文

### 2. 批量分析页面（错误）

**修复前**：
```typescript
research_depth: batchForm.depth,  // 直接传递 "1", "2", "3"
```

❌ 直接传递字符串数字，没有转换

**修复后**：
```typescript
research_depth: getDepthDescription(parseInt(batchForm.depth)),  // 转换为中文
```

✅ 转换为中文字符串

### 3. 定时任务（已优化）

**修复前**：
```python
research_depth="快速",  # 使用快速分析
```

**修复后**：
```python
research_depth="标准",  # 使用标准分析（3级，推荐）
```

✅ 使用更合适的默认深度

## ✅ 修复内容

### 1. 批量分析页面添加转换函数

**文件**：`frontend/src/views/Analysis/BatchAnalysis.vue`

```typescript
// 将数字深度转换为中文描述（与后端保持一致）
const getDepthDescription = (depth: number) => {
  const descriptions = ['快速', '基础', '标准', '深度', '全面']
  return descriptions[depth - 1] || '标准'
}
```

### 2. 批量分析请求参数转换

**文件**：`frontend/src/views/Analysis/BatchAnalysis.vue`

```typescript
parameters: {
  research_depth: getDepthDescription(parseInt(batchForm.depth)),  // 转换为中文
  // ... 其他参数
}
```

### 3. 定时任务默认深度优化

**文件**：`app/worker/watchlist_analysis_task.py`

```python
# 创建分析参数（使用标准分析配置 - 3级）
# 注意：前端使用数字1-5表示深度，后端使用中文"快速/基础/标准/深度/全面"
# 这里使用"标准"（对应前端的3级），平衡速度和质量
parameters = AnalysisParameters(
    market_type="A股",
    research_depth="标准",  # 3级 - 标准分析（推荐）
    selected_analysts=["market", "fundamentals"]
)
```

## 📊 映射关系

| 前端显示 | 前端值 | 后端值 | 配置 |
|---------|-------|--------|------|
| 1级 - 快速分析 | `1` | `"快速"` | 1轮辩论，无记忆 |
| 2级 - 基础分析 | `2` | `"基础"` | 1轮辩论，有记忆 |
| 3级 - 标准分析 | `3` | `"标准"` | 1轮辩论，2轮风险讨论（推荐） |
| 4级 - 深度分析 | `4` | `"深度"` | 2轮辩论，2轮风险讨论 |
| 5级 - 全面分析 | `5` | `"全面"` | 3轮辩论，3轮风险讨论 |

## 🔧 后端兼容性

后端 `create_analysis_config()` 函数已经支持多种格式：

1. **数字格式**：`1, 2, 3, 4, 5`
2. **字符串数字**：`"1", "2", "3", "4", "5"`
3. **中文格式**：`"快速", "基础", "标准", "深度", "全面"`

<augment_code_snippet path="app/services/simple_analysis_service.py" mode="EXCERPT">
````python
# 支持数字和中文两种格式
numeric_to_chinese = {
    1: "快速",
    2: "基础", 
    3: "标准",
    4: "深度",
    5: "全面"
}

if isinstance(research_depth, int):
    research_depth = numeric_to_chinese.get(research_depth, "标准")
elif isinstance(research_depth, str):
    if research_depth.isdigit():
        research_depth = numeric_to_chinese.get(int(research_depth), "标准")
````
</augment_code_snippet>

## 📝 相关文档

- [研究深度映射规范](../design/research_depth_mapping.md) - 完整的映射关系文档
- [研究深度5级别修复](./research_depth_5_levels.md) - 5级别系统的实现
- [模型映射修复](./model/research_depth_mapping_fix.md) - 数据深度映射修复

## ✅ 验证

### 1. 单股分析
- ✅ 前端选择"3级 - 标准分析"
- ✅ 后端接收 `research_depth: "标准"`
- ✅ 报告显示 `"research_depth": "标准"`

### 2. 批量分析
- ✅ 前端选择"3级 - 标准分析"
- ✅ 转换为 `research_depth: "标准"`
- ✅ 后端正确处理

### 3. 定时任务
- ✅ 使用 `research_depth: "标准"`
- ✅ 平衡速度和质量

## 🎯 最佳实践

1. **前端统一转换**：所有前端页面都应使用 `getDepthDescription()` 转换
2. **后端兼容处理**：后端支持多种格式，确保向后兼容
3. **默认值选择**：推荐使用"标准"（3级）作为默认值
4. **文档同步**：保持文档与代码一致

## 📅 修复日期

2025-12-03

