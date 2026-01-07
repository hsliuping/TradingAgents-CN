# 分析师动态裁剪功能修复总结

## 🐛 问题描述

v2.0 工作流引擎在执行股票分析时，即使前端只选择了部分分析师（如"市场分析师"和"基本面分析师"），后端仍然会运行所有分析师（包括"新闻分析师"和"社媒分析师"）。

## 🔍 根本原因

`selected_analysts` 参数没有正确传递到 `WorkflowBuilder`，导致工作流过滤逻辑无法生效。

## ✅ 修复内容

### 1. 后端修复

#### `app/services/unified_analysis_engine.py` (第 381-400 行)
```python
# 🔑 关键：从任务参数中提取 selected_analysts（用于动态裁剪工作流）
if "selected_analysts" in workflow_inputs:
    legacy_config["selected_analysts"] = workflow_inputs["selected_analysts"]
    self.logger.info(f"🎯 选中的分析师: {workflow_inputs['selected_analysts']}")
```

#### `app/routers/workflows.py`
1. **添加字段到 `WorkflowExecuteRequest`** (第 85-102 行):
```python
class WorkflowExecuteRequest(BaseModel):
    # ... 其他字段 ...
    selected_analysts: Optional[List[str]] = Field(
        default=None,
        description="选中的分析师列表，如 ['market', 'fundamentals']"
    )
```

2. **更新 `_build_legacy_config` 函数** (第 732-750 行):
```python
# 🔑 添加 selected_analysts（用于动态裁剪工作流）
if data.selected_analysts:
    config["selected_analysts"] = data.selected_analysts
    logger.info(f"[工作流执行] 选中的分析师: {data.selected_analysts}")
```

### 2. 前端修复

#### `frontend/src/views/Workflow/Execute.vue`
1. **添加字段到 `inputs`** (第 221-230 行):
```typescript
const inputs = ref({
  // ... 其他字段 ...
  selected_analysts: ['market', 'fundamentals', 'news', 'social'], // 默认选中所有
})
```

2. **传递参数到 API** (第 339-349 行):
```typescript
const result = await workflowApi.execute(workflowId.value, {
  // ... 其他参数 ...
  selected_analysts: inputs.value.selected_analysts,
})
```

## 🧪 测试验证

### 自动化测试
```bash
python scripts/test_analyst_filtering.py
```

### 手动测试
1. 打开前端单股分析页面
2. 选择股票代码（如 `000858`）
3. 只勾选"市场分析师"和"基本面分析师"
4. 点击"开始分析"
5. 观察后端日志，确认只运行选中的分析师

### 预期结果
```
✅ 市场分析师报告已生成
✅ 基本面分析师报告已生成
✅ 新闻分析师报告正确跳过
✅ 社媒分析师报告正确跳过
```

## 📊 影响范围

### 修改的文件
- ✅ `app/services/unified_analysis_engine.py`
- ✅ `app/routers/workflows.py`
- ✅ `frontend/src/views/Workflow/Execute.vue`

### 不需要修改的文件
- ✅ `core/workflow/builder.py` - 过滤逻辑已正确实现
- ✅ `frontend/src/views/Analysis/SingleAnalysis.vue` - 前端传参正确
- ✅ `app/routers/analysis.py` - 路由层传参正确

## 📚 相关文档

- 详细修复文档: `docs/bugfix/analyst_filtering_fix.md`
- 测试脚本: `scripts/test_analyst_filtering.py`
- 工作流构建器: `core/workflow/builder.py`

---

**修复日期**: 2026-01-07  
**修复人员**: Augment AI  
**状态**: ✅ 已完成

