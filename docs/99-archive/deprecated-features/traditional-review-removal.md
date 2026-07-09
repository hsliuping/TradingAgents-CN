# 移除交易复盘传统模式

## 📋 变更概述

**日期**: 2025-12-31  
**类型**: 功能简化  
**影响范围**: 交易复盘功能

## 🎯 变更内容

移除交易复盘的"传统分析（快速）"模式选项，统一使用"工作流分析（深度）"模式（任务中心模式）。

### 变更前

用户在创建交易复盘时需要选择分析模式：
- **v1.0 传统分析（快速）**: 同步执行，等待完成后返回结果
- **v2.0 工作流分析（深度）**: 异步执行，支持进度查询

### 变更后

所有交易复盘统一使用任务中心模式：
- **统一模式**: 异步执行，立即返回任务ID
- **进度查询**: 通过 `/api/v1/analysis/tasks/{task_id}` 查询进度
- **更好体验**: 不阻塞UI，支持实时进度跟踪

## 💡 变更理由

### 1. 简化用户体验
- ❌ **变更前**: 用户需要理解两种模式的区别，容易困惑
- ✅ **变更后**: 只有一种模式，用户无需选择

### 2. 统一架构
- ❌ **变更前**: 持仓分析使用任务中心，交易复盘有两种模式
- ✅ **变更后**: 所有分析功能统一使用任务中心

### 3. 更好的可观测性
- ❌ **变更前**: 传统模式无法查询进度，无任务记录
- ✅ **变更后**: 所有任务都有完整的状态跟踪和历史记录

### 4. 降低维护成本
- ❌ **变更前**: 需要维护两套代码路径
- ✅ **变更后**: 单一代码路径，更易维护

## 📝 代码变更

### 1. 路由层 (`app/routers/review.py`)

**变更前**:
```python
# 判断是否使用任务中心模式
use_task_center = request.use_workflow
if use_task_center is None:
    use_task_center = os.getenv("USE_WORKFLOW_REVIEW", "false").lower() == "true"

if use_task_center:
    # 任务中心模式
    ...
else:
    # 传统模式
    service = get_trade_review_service()
    result = await service.create_trade_review(...)
```

**变更后**:
```python
# 统一使用任务中心模式
from app.services.unified_analysis_service import get_unified_analysis_service

unified_service = get_unified_analysis_service()
result = await unified_service.create_trade_review_task(...)

# 后台执行
asyncio.create_task(
    unified_service.execute_trade_review(...)
)
```

### 2. API文档更新

**变更前**:
```
- use_workflow: 是否使用任务中心模式（True=异步，False=同步）

任务中心模式（use_workflow=True）：
- 立即返回任务ID，后台执行复盘
- 支持实时进度跟踪

传统模式（use_workflow=False）：
- 等待复盘完成后返回完整结果
- 适用于快速复盘场景
```

**变更后**:
```
- use_workflow: 是否使用工作流引擎（默认True，推荐）

任务中心模式特点：
- 立即返回任务ID，后台执行复盘
- 支持实时进度跟踪
- 使用工作流引擎进行多智能体协作分析
```

## 🔄 迁移指南

### 前端变更

#### 1. 移除分析模式选择UI

**变更前**:
```jsx
<Radio.Group>
  <Radio value="v1.0">传统分析（快速）</Radio>
  <Radio value="v2.0">工作流分析（深度）</Radio>
</Radio.Group>
```

**变更后**:
```jsx
<!-- 移除选择，默认使用工作流分析 -->
```

#### 2. 调整API调用

**变更前**:
```javascript
// 传统模式：等待完成
const result = await api.post('/api/v1/review/trade', {
  trade_ids: [...],
  use_workflow: false  // 传统模式
});
// result 包含完整的复盘结果

// 任务中心模式：查询进度
const task = await api.post('/api/v1/review/trade', {
  trade_ids: [...],
  use_workflow: true  // 任务中心模式
});
// 轮询查询进度
const progress = await api.get(`/api/v1/analysis/tasks/${task.task_id}`);
```

**变更后**:
```javascript
// 统一使用任务中心模式
const task = await api.post('/api/v1/review/trade', {
  trade_ids: [...]
  // use_workflow 参数仍然支持，但默认为 true
});

// 轮询查询进度
const progress = await api.get(`/api/v1/analysis/tasks/${task.task_id}`);
```

### 后端变更

#### 环境变量（可选）

移除或忽略以下环境变量：
```bash
# 已废弃，不再使用
USE_WORKFLOW_REVIEW=true
```

## ✅ 测试验证

### 1. 功能测试
- [x] 创建交易复盘任务成功
- [x] 任务ID正确返回
- [x] 后台任务正常执行
- [x] 进度查询API正常工作
- [x] 任务完成后结果正确

### 2. 兼容性测试
- [x] 现有API接口保持兼容
- [x] `use_workflow` 参数仍然支持（但始终使用任务中心模式）
- [x] 返回数据格式保持一致

## 📊 影响评估

### 正面影响
- ✅ 用户体验更简洁
- ✅ 代码更易维护
- ✅ 所有任务可追踪
- ✅ 统一的架构设计

### 潜在影响
- ⚠️ 所有复盘都是异步执行（但这是更好的用户体验）
- ⚠️ 前端需要实现进度查询UI（如果还没有）

### 风险缓解
- ✅ API接口保持向后兼容
- ✅ 详细的日志记录便于调试
- ✅ 完整的测试覆盖

## 🔗 相关文档

- [交易复盘任务中心集成设计](../design/v2.0/trade-review-task-center-integration.md)
- [日志指南](../development/logging-guide-trade-review-task-center.md)
- [统一分析服务架构](../design/v2.0/unified-analysis-service.md)

