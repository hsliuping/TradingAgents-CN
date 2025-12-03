# 研究深度映射规范

## 📋 概述

本文档定义了前端和后端之间研究深度（Research Depth）的映射关系，确保整个系统使用一致的深度表示。

## 🔄 映射关系

### 前端 → 后端映射

| 前端显示 | 前端值 | 后端值 | 说明 | 预计时间 |
|---------|-------|--------|------|---------|
| 1级 - 快速分析 | `1` (number) | `"快速"` (string) | 基础数据源，快速决策 | 2-5分钟 |
| 2级 - 基础分析 | `2` (number) | `"基础"` (string) | 常规投资决策 | 3-6分钟 |
| 3级 - 标准分析 | `3` (number) | `"标准"` (string) | 技术+基本面，推荐 | 4-8分钟 |
| 4级 - 深度分析 | `4` (number) | `"深度"` (string) | 多轮辩论，深度研究 | 6-11分钟 |
| 5级 - 全面分析 | `5` (number) | `"全面"` (string) | 最全面的分析报告 | 8-16分钟 |

### 转换函数

#### 前端转换（TypeScript）

```typescript
// frontend/src/views/Analysis/SingleAnalysis.vue
const getDepthDescription = (depth: number) => {
  const descriptions = ['快速', '基础', '标准', '深度', '全面']
  return descriptions[depth - 1] || '标准'
}
```

#### 后端转换（Python）

```python
# app/services/simple_analysis_service.py
def create_analysis_config(research_depth, ...):
    # 支持数字和中文两种格式
    numeric_to_chinese = {
        1: "快速",
        2: "基础", 
        3: "标准",
        4: "深度",
        5: "全面"
    }
    
    if isinstance(research_depth, int):
        if research_depth in numeric_to_chinese:
            research_depth = numeric_to_chinese[research_depth]
        else:
            research_depth = "标准"  # 默认值
```

## 📊 各级别配置详情

### 1级 - 快速分析

```python
{
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "memory_enabled": False,
    "online_tools": True
}
```

**特点**：
- ⚡ 最快速度
- 📊 基础数据源
- 🎯 单轮分析
- 💾 不启用记忆

### 2级 - 基础分析

```python
{
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "memory_enabled": True,
    "online_tools": True
}
```

**特点**：
- 📈 常规投资决策
- 💾 启用记忆
- 🎯 单轮分析
- 🌐 在线数据

### 3级 - 标准分析（推荐）

```python
{
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 2,
    "memory_enabled": True,
    "online_tools": True
}
```

**特点**：
- 🎯 平衡速度和质量
- 📊 技术+基本面
- 🔍 2轮风险讨论
- ⭐ **推荐使用**

### 4级 - 深度分析

```python
{
    "max_debate_rounds": 2,
    "max_risk_discuss_rounds": 2,
    "memory_enabled": True,
    "online_tools": True
}
```

**特点**：
- 🔍 多轮辩论
- 📊 深度研究
- 💡 多角度分析
- 🎯 适合重要决策

### 5级 - 全面分析

```python
{
    "max_debate_rounds": 3,
    "max_risk_discuss_rounds": 3,
    "memory_enabled": True,
    "online_tools": True
}
```

**特点**：
- 🏆 最全面分析
- 📊 所有数据源
- 💡 3轮深度辩论
- ⏱️ 耗时最长

## 🔧 使用示例

### 前端调用

```typescript
// SingleAnalysis.vue
const request: SingleAnalysisRequest = {
  symbol: '000001',
  parameters: {
    research_depth: getDepthDescription(analysisForm.researchDepth), // 转换为中文
    // ... 其他参数
  }
}
```

### 后端接收

```python
# app/services/simple_analysis_service.py
async def analyze_stock(request: SingleAnalysisRequest):
    # 自动处理数字或中文格式
    research_depth = request.parameters.research_depth  # "标准" 或 3
    config = create_analysis_config(research_depth, ...)
```

## ⚠️ 注意事项

1. **前端必须转换**：前端发送请求时，必须将数字转换为中文字符串
2. **后端兼容性**：后端同时支持数字和中文格式，但内部统一使用中文
3. **默认值**：当深度值无效时，默认使用"标准"（3级）
4. **定时任务**：定时任务应使用"标准"作为默认深度

## 📝 相关文件

### 前端文件
- `frontend/src/views/Analysis/SingleAnalysis.vue` - 单股分析页面
- `frontend/src/views/Analysis/BatchAnalysis.vue` - 批量分析页面
- `frontend/src/constants/analysts.ts` - 常量定义

### 后端文件
- `app/services/simple_analysis_service.py` - 分析服务（核心转换逻辑）
- `app/models/analysis.py` - 数据模型定义
- `app/worker/watchlist_analysis_task.py` - 定时任务
- `tests/test_research_depth_mapping.py` - 映射测试

## 🧪 测试

运行测试确保映射正确：

```bash
pytest tests/test_research_depth_mapping.py -v
```

测试覆盖：
- ✅ 数字格式转换（1-5）
- ✅ 中文格式直接使用
- ✅ 字符串数字转换（"1"-"5"）
- ✅ 无效值默认处理

