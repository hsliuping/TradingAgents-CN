# 持仓分析改造：使用统一任务中心

## 改造目标

将持仓分析功能改造为使用新的统一任务中心（`unified_analysis_tasks` 集合），实现与股票分析一致的任务管理和进度跟踪。

## 改造内容

### 1. 统一分析服务扩展

**文件**：`app/services/unified_analysis_service.py`

**新增方法**：

#### `create_position_analysis_task()`
创建持仓分析任务，保存到统一任务中心。

```python
async def create_position_analysis_task(
    self,
    user_id: str,
    code: str,
    market: str = "CN",
    task_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """创建持仓分析任务"""
```

**功能**：
- 创建 `UnifiedAnalysisTask` 对象
- 任务类型：`AnalysisTaskType.POSITION_ANALYSIS`
- 引擎类型：`v2`（使用 v2.0 引擎）
- 保存到 `unified_analysis_tasks` 集合
- 保存到内存状态管理器

#### `execute_position_analysis()`
执行持仓分析任务。

```python
async def execute_position_analysis(
    self,
    task_id: str,
    user_id: str,
    code: str,
    market: str = "CN",
    task_params: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """执行持仓分析"""
```

**功能**：
- 更新任务状态为 `PROCESSING`
- 调用 `portfolio_service.analyze_position_by_code()` 执行分析
- 更新任务状态为 `COMPLETED` 或 `FAILED`
- 保存分析结果到任务的 `result` 字段

#### `_update_position_task_status()`
更新持仓分析任务状态。

```python
async def _update_position_task_status(
    self,
    task_id: str,
    status: AnalysisStatus,
    message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
):
    """更新持仓分析任务状态"""
```

**功能**：
- 更新数据库中的任务状态
- 更新内存状态管理器

### 2. API 路由修改

**文件**：`app/routers/portfolio.py`

#### `POST /api/portfolio/positions/analyze-by-code`
创建持仓分析任务。

**修改前**：
- 调用 `portfolio_service.create_position_analysis_task()`
- 返回 `analysis_id`

**修改后**：
- 调用 `unified_service.create_position_analysis_task()`
- 返回 `task_id`
- 后台执行 `unified_service.execute_position_analysis()`

#### `GET /api/portfolio/positions/analysis/{task_id}`
获取持仓分析任务状态和结果。

**修改前**：
- 从 `position_analysis_reports` 集合查询
- 使用 `analysis_id` 查询

**修改后**：
- 从 `unified_analysis_tasks` 集合查询
- 使用 `task_id` 查询
- 返回统一的任务状态格式

### 3. 数据流程

#### 创建任务流程

```
用户请求
  ↓
POST /api/portfolio/positions/analyze-by-code
  ↓
unified_service.create_position_analysis_task()
  ↓
创建 UnifiedAnalysisTask
  ↓
保存到 unified_analysis_tasks 集合
  ↓
保存到内存状态管理器
  ↓
返回 task_id
  ↓
后台执行 execute_position_analysis()
```

#### 执行任务流程

```
execute_position_analysis()
  ↓
更新任务状态为 PROCESSING
  ↓
调用 portfolio_service.analyze_position_by_code()
  ↓
  ├─ 查询持仓记录
  ├─ 汇总计算持仓数据
  ├─ 调用单股分析服务
  ├─ 调用持仓分析 AI
  └─ 生成分析报告
  ↓
更新任务状态为 COMPLETED/FAILED
  ↓
保存结果到 task.result
```

#### 查询任务流程

```
用户请求
  ↓
GET /api/portfolio/positions/analysis/{task_id}
  ↓
从 unified_analysis_tasks 查询
  ↓
返回任务状态和结果
```

## 向后兼容

- 保留了 `portfolio_service.analyze_position_by_code()` 方法
- 保留了 `position_analysis_reports` 集合（由 `analyze_position_by_code()` 使用）
- 旧的 API 接口仍然可用，但推荐使用新的统一任务中心接口

## 优势

1. **统一管理**：持仓分析任务与股票分析任务使用相同的任务中心
2. **统一查询**：可以使用 `/api/analysis/tasks/{task_id}/status` 查询任务状态
3. **统一进度跟踪**：使用相同的进度跟踪机制
4. **统一错误处理**：使用相同的错误处理和重试机制
5. **更好的可扩展性**：未来可以轻松添加更多分析类型

## 测试建议

1. 测试创建持仓分析任务
2. 测试查询任务状态
3. 测试任务执行完成后的结果
4. 测试任务执行失败的错误处理
5. 测试与股票分析任务的兼容性

