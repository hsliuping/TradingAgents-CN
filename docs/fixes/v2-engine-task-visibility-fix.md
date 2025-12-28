# V2 引擎任务可见性修复

## 🐛 问题描述

### 用户反馈

使用单股分析接口 `/api/analysis/single` 时，参数中指定了 `"engine": "v2"`：

```json
{
    "symbol": "000001",
    "stock_code": "000001",
    "parameters": {
        "market_type": "A股",
        "analysis_date": "2025-12-28",
        "research_depth": "快速",
        "selected_analysts": ["market", "fundamentals"],
        "include_sentiment": true,
        "include_risk": true,
        "language": "zh-CN",
        "quick_analysis_model": "qwen-flash",
        "deep_analysis_model": "qwen-plus",
        "engine": "v2"
    }
}
```

**现象**:
- ✅ 后端能正常分析
- ❌ 新版任务中心 (`/tasks/unified`) 看不到任务
- ✅ 旧版任务中心 (`/tasks`) 可以看到任务

## 🔍 问题分析

### 根本原因

**任务存储不匹配**：

1. **任务创建**：使用 `SimpleAnalysisService.create_analysis_task()`
   - 创建的是旧版 `AnalysisTask` 模型
   - 存储在 `analysis_tasks` 集合

2. **新版任务中心**：查询 `unified_analysis_tasks` 集合
   - 只能看到 `UnifiedAnalysisTask` 模型的任务
   - 看不到 `analysis_tasks` 集合中的任务

3. **旧版任务中心**：查询 `analysis_tasks` 集合
   - 可以看到旧版任务

### 架构问题

**修复前的流程**：

```
用户请求 (engine: "v2")
    ↓
创建任务: SimpleAnalysisService.create_analysis_task()
    ↓
存储: analysis_tasks 集合 (AnalysisTask)
    ↓
执行: UnifiedAnalysisService.execute_analysis_for_v2_engine()
    ↓
结果: 新版任务中心看不到 ❌
```

**问题**：任务创建和执行使用了不同的系统！

## 🛠️ 修复方案

### 核心思路

**当使用 v2 引擎时，应该使用统一任务系统**：

1. **任务创建**：使用 `TaskAnalysisService.create_task()`
   - 创建 `UnifiedAnalysisTask` 模型
   - 存储在 `unified_analysis_tasks` 集合

2. **任务执行**：使用 `TaskAnalysisService.execute_task()`
   - 统一的执行接口
   - 自动选择合适的引擎

3. **任务查询**：新版任务中心可以看到

### 修复后的流程

```
用户请求 (engine: "v2")
    ↓
创建任务: TaskAnalysisService.create_task()
    ↓
存储: unified_analysis_tasks 集合 (UnifiedAnalysisTask)
    ↓
执行: TaskAnalysisService.execute_task()
    ↓
结果: 新版任务中心可以看到 ✅
```

## 📝 代码修改

### 文件：`app/routers/analysis.py`

#### 1. 单股分析 - 任务创建

**修改前**：
```python
# 所有引擎都使用旧服务创建任务
legacy_service = get_simple_analysis_service()
result = await legacy_service.create_analysis_task(user["id"], request)
task_id = result["task_id"]
```

**修改后**：
```python
# 根据引擎类型选择任务创建方式
if engine_type == AnalysisEngine.V2:
    # v2 引擎：使用统一任务服务
    from app.services.task_analysis_service import get_task_analysis_service
    from app.models.analysis import AnalysisTaskType
    from app.models.user import PyObjectId
    
    task_service = get_task_analysis_service()
    task_params = {
        "symbol": request.get_symbol(),
        "stock_code": request.get_symbol(),
        "parameters": request.parameters.model_dump() if request.parameters else {}
    }
    
    task = await task_service.create_task(
        user_id=PyObjectId(user["id"]),
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params=task_params,
        engine_type="auto",
        preference_type="neutral"
    )
    
    result = {
        "task_id": str(task.id),
        "status": task.status.value,
        "created_at": task.created_at.isoformat() if task.created_at else None
    }
    task_id = str(task.id)
else:
    # legacy/unified 引擎：使用旧服务
    legacy_service = get_simple_analysis_service()
    result = await legacy_service.create_analysis_task(user["id"], request)
    task_id = result["task_id"]
```

#### 2. 单股分析 - 任务执行

**修改前**：
```python
if engine_type == AnalysisEngine.V2:
    unified_service = get_unified_analysis_service()
    await unified_service.execute_analysis_for_v2_engine(
        task_id, user_id, request, progress_tracker=None
    )
```

**修改后**：
```python
if engine_type == AnalysisEngine.V2:
    # v2 引擎：使用统一任务服务执行
    from app.services.task_analysis_service import get_task_analysis_service
    task_service = get_task_analysis_service()
    await task_service.execute_task(task_id)
```

#### 3. 批量分析 - 任务创建和执行

同样的修改应用到批量分析的任务创建和执行部分。

## ✅ 修复效果

### 修复前

| 引擎类型 | 任务集合 | 旧版任务中心 | 新版任务中心 |
|---------|---------|------------|------------|
| legacy  | analysis_tasks | ✅ 可见 | ❌ 不可见 |
| unified | analysis_tasks | ✅ 可见 | ❌ 不可见 |
| v2      | analysis_tasks | ✅ 可见 | ❌ 不可见 |

### 修复后

| 引擎类型 | 任务集合 | 旧版任务中心 | 新版任务中心 |
|---------|---------|------------|------------|
| legacy  | analysis_tasks | ✅ 可见 | ❌ 不可见 |
| unified | analysis_tasks | ✅ 可见 | ❌ 不可见 |
| v2      | unified_analysis_tasks | ❌ 不可见 | ✅ 可见 |

## 📊 影响范围

### 修改的文件

- `app/routers/analysis.py` - 分析路由

### 修改的功能

1. **单股分析** (`POST /api/analysis/single`)
   - 当 `engine: "v2"` 时，使用统一任务系统
   - 任务在新版任务中心可见

2. **批量分析** (`POST /api/analysis/batch`)
   - 当 `engine: "v2"` 时，使用统一任务系统
   - 所有任务在新版任务中心可见

### 不影响的功能

- `engine: "legacy"` - 继续使用旧系统，旧版任务中心可见
- `engine: "unified"` - 继续使用旧系统，旧版任务中心可见
- 旧版任务中心 (`/tasks`) - 继续正常工作

## 🎯 验证步骤

### 1. 测试 v2 引擎单股分析

```bash
curl -X POST http://127.0.0.1:3000/api/analysis/single \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbol": "000001",
    "parameters": {
      "engine": "v2",
      "research_depth": "快速",
      "selected_analysts": ["market"]
    }
  }'
```

**预期结果**：
- ✅ 返回任务ID
- ✅ 新版任务中心 (`/tasks/unified`) 可以看到任务
- ✅ 任务状态实时更新

### 2. 测试 legacy 引擎（确保不受影响）

```bash
curl -X POST http://127.0.0.1:3000/api/analysis/single \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbol": "000001",
    "parameters": {
      "engine": "legacy",
      "research_depth": "快速"
    }
  }'
```

**预期结果**：
- ✅ 返回任务ID
- ✅ 旧版任务中心 (`/tasks`) 可以看到任务
- ✅ 任务正常执行

### 3. 前端验证

1. 访问 `/stocks/000001/detail`
2. 点击"分析"按钮
3. 选择引擎类型为 "v2"
4. 提交分析
5. 访问 `/tasks/unified`
6. 确认可以看到刚创建的任务

## 🔄 迁移建议

### 短期（当前）

- ✅ v2 引擎使用新系统
- ✅ legacy/unified 引擎继续使用旧系统
- ✅ 两个任务中心并存

### 中期（未来）

1. **逐步迁移**：将 legacy 和 unified 引擎也迁移到统一任务系统
2. **统一任务中心**：只保留新版任务中心
3. **数据迁移**：将旧任务数据迁移到新集合

### 长期（最终）

- 🎯 只使用统一任务系统
- 🎯 只有一个任务中心
- 🎯 所有任务都在 `unified_analysis_tasks` 集合

## 📚 相关文档

- [统一任务中心实施文档](../design/unified-task-center-implementation.md)
- [分析任务优化方案](../design/analysis-task-optimization.md)
- [任务服务集成指南](../design/task-service-integration-guide.md)

## ✨ 总结

这次修复解决了 v2 引擎任务在新版任务中心不可见的问题，核心思路是：

1. **任务创建和执行使用同一个系统**
2. **v2 引擎使用统一任务系统**
3. **保持向后兼容，不影响现有功能**

现在用户使用 v2 引擎时，可以在新版任务中心看到任务了！🎉



